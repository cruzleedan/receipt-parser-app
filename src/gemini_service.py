"""
Receipt parsing using Google Gemini's vision API.

Single-stage: sends the receipt image directly to Gemini and asks for
structured JSON, skipping the OCR + local LLM pipeline entirely.
"""

import asyncio
import json
import logging
import re
import time
from io import BytesIO
from typing import Any, Dict

from google import genai
from google.genai import types
from PIL import Image

from src.models import ReceiptData, ExtractionOptions
from src.config import settings
from src.extraction import generic_prompt
from src.vlm_service import to_receipt
from src.workers import image_worker

logger = logging.getLogger(__name__)


class GeminiReceiptService:
    """
    Receipt parser using Gemini's multimodal API for combined OCR + extraction.
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model

        if not self.api_key:
            raise ValueError("Gemini API key is not configured")

        # WORK-0005: GEMINI_TIMEOUT now applies (the SDK takes milliseconds).
        self.timeout_seconds = settings.gemini_timeout
        # Setting http_options drops the SDK's default v1beta; JSON mode needs v1beta.
        self.http_options = types.HttpOptions(
            api_version="v1beta", timeout=int(self.timeout_seconds * 1000)
        )
        self.client = genai.Client(api_key=self.api_key, http_options=self.http_options)

        logger.info(f"Initialized Gemini client (model: {self.model})")

    async def parse_receipt(
        self,
        image: Image.Image,
        max_retries: int = 2,
        extraction_options: ExtractionOptions = None,
        deadline: float | None = None,
        reserve_seconds: float = 0.0,
    ) -> ReceiptData:
        """
        Parse a receipt image into structured data using Gemini.

        Args:
            image: PIL Image object
            max_retries: Maximum number of retry attempts
            extraction_options: Options controlling which fields to extract
            deadline: time.monotonic() value by which the whole parse must end
            reserve_seconds: time to leave before the deadline for the fallback

        Returns:
            ReceiptData object

        Raises:
            RuntimeError: If parsing fails after retries
        """
        if extraction_options is None:
            extraction_options = ExtractionOptions()

        primary_deadline = min(
            time.monotonic() + self.timeout_seconds * max_retries + 3,
            deadline - reserve_seconds if deadline is not None else float("inf"),
        )
        if primary_deadline - time.monotonic() < 1:
            raise RuntimeError("Gemini parsing skipped: parse deadline too close")
        async with asyncio.timeout_at(primary_deadline):
            image_bytes = await image_worker.run(self._image_to_bytes, image)
        prompt = self._build_prompt(extraction_options)

        last_error: Exception | None = None

        for attempt in range(max_retries):
            budget = self.timeout_seconds
            if deadline is not None:
                budget = min(budget, deadline - time.monotonic() - reserve_seconds)
                if budget < 1:
                    logger.warning("Gemini skipped: not enough time left before the fallback reserve")
                    break
            try:
                response_text = await asyncio.wait_for(
                    self._call_gemini(prompt, image_bytes), timeout=budget
                )
                return self._parse_response(response_text)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Gemini parsing attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        if last_error is None:
            raise RuntimeError("Gemini parsing skipped: parse deadline too close")
        logger.error(f"Gemini parsing failed after {max_retries} attempts")
        raise RuntimeError(f"Gemini parsing failed: {str(last_error)}")

    async def health_check(self) -> Dict[str, Any]:
        """Check Gemini service configuration/health."""
        if not self.api_key:
            return {
                "status": "error",
                "backend": "Gemini",
                "error": "API key not configured",
            }

        return {
            "status": "connected",
            "backend": "Gemini",
            "model": self.model,
        }

    async def _call_gemini(self, prompt: str, image_bytes: bytes) -> str:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )

            if response.candidates and str(response.candidates[0].finish_reason).split(".")[-1] == "MAX_TOKENS":
                raise ValueError("Gemini extraction incomplete: output token limit reached")
            text = response.text
            if not text:
                raise RuntimeError("Empty response from Gemini")

            return text
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {str(e)}")

    def _parse_response(self, response: str) -> ReceiptData:
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Gemini response is not valid JSON, attempting to extract...")
            data = self._extract_json_from_text(response)

        try:
            return to_receipt(data)
        except Exception as e:
            logger.error(f"Response validation failed: {e}")
            logger.debug(f"Raw response: {response}")
            raise ValueError(f"Invalid receipt data: {str(e)}")

    @staticmethod
    def _extract_json_from_text(text: str) -> dict:
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError("No valid JSON found in response")

    @staticmethod
    def _image_to_bytes(image: Image.Image) -> bytes:
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _build_prompt(options: ExtractionOptions = None) -> str:
        if options is None:
            options = ExtractionOptions()

        return generic_prompt(options) + " Extract every purchased line item when requested."
