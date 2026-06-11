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

        self.client = genai.Client(api_key=self.api_key)

        logger.info(f"Initialized Gemini client (model: {self.model})")

    async def parse_receipt(
        self,
        image: Image.Image,
        max_retries: int = 2,
        extraction_options: ExtractionOptions = None,
    ) -> ReceiptData:
        """
        Parse a receipt image into structured data using Gemini.

        Args:
            image: PIL Image object
            max_retries: Maximum number of retry attempts
            extraction_options: Options controlling which fields to extract

        Returns:
            ReceiptData object

        Raises:
            RuntimeError: If parsing fails after retries
        """
        if extraction_options is None:
            extraction_options = ExtractionOptions()

        image_bytes = self._image_to_bytes(image)
        prompt = self._build_prompt(extraction_options)

        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                response_text = await asyncio.to_thread(
                    self._call_gemini, prompt, image_bytes
                )
                return self._parse_response(response_text)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Gemini parsing attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

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

    def _call_gemini(self, prompt: str, image_bytes: bytes) -> str:
        try:
            response = self.client.models.generate_content(
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
            return ReceiptData(**data)
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

        json_parts = ['"merchant_name":"store name"']
        rules = ["- merchant_name: Business name from receipt header (first few lines)"]

        if options.merchant_address:
            json_parts.append('"merchant_address":"address or null"')
            rules.append("- merchant_address: Full address if shown, or null")

        if options.merchant_phone:
            json_parts.append('"merchant_phone":"phone or null"')
            rules.append("- merchant_phone: Phone number if shown, or null")

        if options.date:
            json_parts.append('"date":"YYYY-MM-DD"')
            rules.append("- date: Convert to YYYY-MM-DD format. Use null if no date is explicitly shown")

        if options.time:
            json_parts.append('"time":"HH:MM"')
            rules.append("- time: Convert to HH:MM 24h format. Use null if no time is explicitly shown")

        if options.items:
            json_parts.append('"items":[{"name":"product","quantity":1,"total_price":0.00}]')
            rules.append("- items: Up to 10 products with name and total_price")

        if options.subtotal:
            json_parts.append('"subtotal":0.00')
            rules.append("- subtotal: Pre-tax amount, or null if not shown")

        if options.tax:
            json_parts.append('"tax":0.00')
            rules.append("- tax: Tax/VAT amount, or null if not shown")

        if options.tip:
            json_parts.append('"tip":0.00')
            rules.append("- tip: Tip/gratuity amount, or null if not shown")

        if options.discount:
            json_parts.append('"discount":0.00')
            rules.append("- discount: Discount amount, or null if not shown")

        json_parts.append('"total":0.00')
        rules.append("- total: IMPORTANT - This is the final amount the customer pays. Look for the largest total near the bottom.")

        if options.payment_method:
            json_parts.append('"payment_method":"cash/card/etc"')
            rules.append("- payment_method: Payment type if shown, or null")

        if options.receipt_number:
            json_parts.append('"receipt_number":"number or null"')
            rules.append("- receipt_number: Transaction/receipt number if shown, or null")

        if options.cashier:
            json_parts.append('"cashier":"name or null"')
            rules.append("- cashier: Cashier name if shown, or null")

        json_structure = "{" + ",".join(json_parts) + "}"
        rules_text = "\n".join(rules)

        return f"""You are a receipt parser. Extract data from this receipt image and return JSON.

Return this JSON structure:
{json_structure}

Extraction rules:
{rules_text}

IMPORTANT: Only extract information that is actually visible in the image. Use null for missing values. Do not fabricate values.

JSON:"""
