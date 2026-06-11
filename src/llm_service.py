"""
LLM Service using Ollama for structured JSON extraction from OCR text.
"""

import asyncio
import json
import logging
import re
import time
from typing import Dict, Any

import requests

from src.models import ReceiptData, ExtractionOptions
from src.config import settings

OCR_TEXT_MAX_CHARS = 4000

logger = logging.getLogger(__name__)


class OllamaLLMService:
    """
    LLM service for extracting structured JSON from OCR text using Ollama.

    Features:
    - JSON schema enforcement
    - Retry logic with exponential backoff
    - Response validation
    - CPU-optimized inference
    """

    def __init__(self, host: str = None, model: str = None):
        """
        Initialize Ollama client.

        Args:
            host: Ollama API host (defaults to settings.ollama_host)
            model: Model name (defaults to settings.ollama_model)
        """
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        self.api_url = f"{self.host}/api/generate"

        logger.info(f"Initialized Ollama client (host: {self.host}, model: {self.model})")

    async def parse_receipt(
        self,
        ocr_text: str,
        max_retries: int = 3,
        extraction_options: ExtractionOptions = None,
    ) -> ReceiptData:
        """
        Parse OCR text into structured receipt data.

        Args:
            ocr_text: Raw text from OCR
            max_retries: Maximum number of retry attempts
            extraction_options: Options controlling which fields to extract

        Returns:
            ReceiptData object

        Raises:
            RuntimeError: If parsing fails after retries
        """
        if extraction_options is None:
            extraction_options = ExtractionOptions()

        # Cap input to prevent context overflow and prompt injection surface
        if len(ocr_text) > OCR_TEXT_MAX_CHARS:
            logger.warning(
                f"OCR text truncated from {len(ocr_text)} to {OCR_TEXT_MAX_CHARS} chars"
            )
            ocr_text = ocr_text[:OCR_TEXT_MAX_CHARS]

        start_time = time.time()

        for attempt in range(max_retries):
            try:
                prompt = self._build_prompt(ocr_text, extraction_options)
                response = self._call_ollama(prompt)
                receipt_data = self._parse_response(response)

                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"LLM parsing completed in {elapsed_ms:.0f}ms")

                return receipt_data

            except Exception as e:
                logger.warning(
                    f"LLM parsing attempt {attempt + 1}/{max_retries} failed: {e}"
                )

                if attempt == max_retries - 1:
                    logger.error(f"LLM parsing failed after {max_retries} attempts")
                    raise RuntimeError(f"LLM parsing failed: {str(e)}")

                await asyncio.sleep(2**attempt)

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Ollama service health.

        Returns:
            Health status dictionary
        """
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]

            model_available = any(
                self.model in name or name.startswith(self.model.split(":")[0])
                for name in model_names
            )

            return {
                "status": "connected",
                "backend": "Ollama",
                "model": self.model,
                "model_available": model_available,
                "host": self.host,
            }

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "host": self.host,
            }

    def _build_prompt(self, ocr_text: str, options: ExtractionOptions = None) -> str:
        """
        Build prompt for Ollama with JSON schema based on extraction options.

        Args:
            ocr_text: Raw OCR text
            options: Extraction options controlling which fields to extract

        Returns:
            Formatted prompt string
        """
        if options is None:
            options = ExtractionOptions()

        # Build dynamic JSON structure based on options
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

        return f"""You are a receipt parser. Extract data from this receipt text and return JSON.

{ocr_text.strip()}

Return this JSON structure:
{json_structure}

Extraction rules:
{rules_text}

IMPORTANT: Only extract information that is actually present in the text. Use null for missing values. Do not fabricate values.

JSON:"""

    def _call_ollama(self, prompt: str) -> str:
        """
        Call Ollama API to generate response.

        Args:
            prompt: Input prompt

        Returns:
            Generated text response

        Raises:
            RuntimeError: If API call fails
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "keep_alive": "10m",  # Keep model loaded
                "options": {
                    "temperature": 0,
                    "top_p": 0.9,
                    "num_predict": 768,
                    "num_ctx": 1536,
                    "num_thread": 20,
                    "num_batch": 512,
                    "num_gpu": 99 if settings.ocr_use_gpu else 0,
                },
            }

            response = requests.post(
                self.api_url, json=payload, timeout=settings.ollama_timeout
            )
            response.raise_for_status()

            result = response.json()
            generated_text = result.get("response", "")

            if not generated_text:
                raise RuntimeError("Empty response from Ollama")

            return generated_text

        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API call failed: {e}")
            raise RuntimeError(f"Ollama API error: {str(e)}")

    def _parse_response(self, response: str) -> ReceiptData:
        """
        Parse Ollama response into ReceiptData.

        Args:
            response: Generated JSON string

        Returns:
            Validated ReceiptData object

        Raises:
            ValueError: If response is invalid JSON or doesn't match schema
        """
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code blocks
            logger.warning("Response is not valid JSON, attempting to extract...")
            data = self._extract_json_from_text(response)

        # Validate using Pydantic model
        try:
            return ReceiptData(**data)
        except Exception as e:
            logger.error(f"Response validation failed: {e}")
            logger.debug(f"Raw response: {response}")
            raise ValueError(f"Invalid receipt data: {str(e)}")

    @staticmethod
    def _extract_json_from_text(text: str) -> dict:
        """
        Extract JSON object from text (handles markdown code blocks).

        Args:
            text: Text containing JSON

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If no valid JSON found
        """
        # Try extracting from ```json code blocks
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Try finding any JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError("No valid JSON found in response")
