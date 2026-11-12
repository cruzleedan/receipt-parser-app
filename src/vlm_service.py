"""
WORK-0008: receipt parsing with one local vision-language model in Ollama.

The model reads the image and answers JSON in one call. Two prompt styles:
- generic (e.g. qwen3.5:4b): an instruction prompt plus Ollama's JSON-schema `format`;
- NuExtract (numind/nuextract3): its own message roles, a typed template and instructions.

Dates are asked for exactly as printed and normalised here (month first, as on Philippine
receipts), because models reorder short dates wrongly (WORK-0009: month/day swaps, a two-digit
year read as the day).
"""

import asyncio
import base64
import io
import json
import logging
import time
from typing import Any, Dict, Optional

import requests
from PIL import Image

from src.config import settings
from src.models import ExtractionOptions, ReceiptData
from src.utils import normalise_date

logger = logging.getLogger(__name__)

TOTAL_RULE = (
    "total is the final amount due for the purchase (the line labelled TOTAL, AMOUNT DUE or similar), "
    "not the cash tendered, the change, or the VATable or subtotal amount."
)
MERCHANT_RULE = "merchant_name is the store or business name at the top, not the address or the operator company."
# No example date: models copied the example into answers (WORK-0008).
DATE_RULE = "date is the transaction date copied exactly as printed on the receipt, including the year; do not reorder or convert it."

NUMBER = {"type": ["number", "null"]}
TEXT = {"type": ["string", "null"]}

# field -> (ExtractionOptions flag or None for always, JSON-schema type, NuExtract type)
FIELDS = {
    "merchant_name": (None, TEXT, "verbatim-string"),
    "merchant_address": ("merchant_address", TEXT, "verbatim-string"),
    "merchant_phone": ("merchant_phone", TEXT, "verbatim-string"),
    "date": ("date", TEXT, "verbatim-string"),
    "time": ("time", TEXT, "verbatim-string"),
    "subtotal": ("subtotal", NUMBER, "number"),
    "tax": ("tax", NUMBER, "number"),
    "tip": ("tip", NUMBER, "number"),
    "discount": ("discount", NUMBER, "number"),
    "total": (None, NUMBER, "number"),
    "payment_method": ("payment_method", TEXT, "verbatim-string"),
    "card_last_4": ("payment_method", TEXT, "verbatim-string"),
    "receipt_number": ("receipt_number", TEXT, "verbatim-string"),
    "cashier": ("cashier", TEXT, "verbatim-string"),
}
ITEM_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "quantity": NUMBER, "unit_price": NUMBER, "total_price": NUMBER},
    "required": ["name", "quantity", "unit_price", "total_price"],
}
ITEM_TEMPLATE = {"name": "verbatim-string", "quantity": "number", "unit_price": "number", "total_price": "number"}


def wanted_fields(options: ExtractionOptions) -> list[str]:
    return [f for f, (flag, _, _) in FIELDS.items() if flag is None or getattr(options, flag)]


def json_schema(options: ExtractionOptions) -> Dict[str, Any]:
    """Every key required (null allowed): optional keys get skipped by models (WORK-0009)."""
    fields = wanted_fields(options)
    props = {f: FIELDS[f][1] for f in fields}
    if options.items:
        props["items"] = {"type": "array", "items": ITEM_SCHEMA}
    return {"type": "object", "properties": props, "required": list(props)}


def nuextract_template(options: ExtractionOptions) -> Dict[str, Any]:
    template = {f: FIELDS[f][2] for f in wanted_fields(options)}
    if options.items:
        template["items"] = [ITEM_TEMPLATE]
    return template


def generic_prompt(options: ExtractionOptions) -> str:
    fields = wanted_fields(options) + (["items (each: name, quantity, unit_price, total_price)"] if options.items else [])
    return (
        "Read this receipt and return its data as JSON with these fields: " + ", ".join(fields) + ".\n"
        f"- {MERCHANT_RULE}\n- {DATE_RULE}\n- {TOTAL_RULE}\n"
        "Copy amounts as plain numbers without currency symbols. Use null for anything not printed. "
        "Return only the JSON."
    )


def to_receipt(data: Dict[str, Any]) -> ReceiptData:
    """Clean the model's answer into ReceiptData; raises ValueError when unusable."""
    if not isinstance(data, dict):
        raise ValueError("answer is not a JSON object")
    total = data.get("total")
    if not isinstance(total, (int, float)):
        raise ValueError("no total")
    items = []
    for it in data.get("items") or []:
        if not isinstance(it, dict) or not it.get("name") or not isinstance(it.get("total_price"), (int, float)):
            continue
        qty = it.get("quantity")
        items.append({
            "name": str(it["name"])[:200],
            # ReceiptItem takes whole quantities >= 1; weights such as 0.5 kg become 1.
            "quantity": int(qty) if isinstance(qty, (int, float)) and qty >= 1 and float(qty).is_integer() else None,
            "unit_price": it.get("unit_price") if isinstance(it.get("unit_price"), (int, float)) else None,
            "total_price": float(it["total_price"]),
        })
    clean = {k: data.get(k) for k in FIELDS if k in data}
    clean["merchant_name"] = (data.get("merchant_name") or "").strip() or "Unknown"
    clean["date"] = normalise_date(data.get("date"))
    clean["total"] = float(total)
    for k in ("subtotal", "tax", "tip", "discount"):
        if k in clean and not isinstance(clean[k], (int, float)):
            clean[k] = None
    for k in ("merchant_address", "merchant_phone", "time", "payment_method", "card_last_4", "receipt_number", "cashier"):
        if k in clean and clean[k] is not None:
            clean[k] = str(clean[k])[:200]
    clean["items"] = items
    return ReceiptData(**clean)


class VisionLLMService:
    """One Ollama vision model that reads the receipt image directly."""

    def __init__(self, host: str = None, model: str = None):
        self.host = host or settings.vlm_host
        self.model = model or settings.vlm_model
        self.nuextract = "nuextract" in self.model.lower()
        logger.info(f"Initialized vision model client (host: {self.host}, model: {self.model})")

    async def parse_receipt(
        self, image: Image.Image, extraction_options: ExtractionOptions = None, deadline: Optional[float] = None,
        reserve_seconds: float = 0.0,
    ) -> ReceiptData:
        options = extraction_options or ExtractionOptions()
        timeout = float(settings.vlm_timeout)
        if deadline is not None:
            timeout = min(timeout, deadline - time.monotonic() - reserve_seconds)
            if timeout < 1:
                raise TimeoutError("parse deadline reached before the vision-model call")
        payload = self._payload(image, options)
        started = time.monotonic()
        content = await asyncio.to_thread(self._chat, payload, timeout)
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"vision model answer is not JSON: {e}") from e
        receipt = to_receipt(data)
        logger.info(f"Vision model parsed the receipt in {(time.monotonic() - started) * 1000:.0f}ms")
        return receipt

    def _payload(self, image: Image.Image, options: ExtractionOptions) -> Dict[str, Any]:
        img = image.convert("RGB")
        img.thumbnail((settings.vlm_max_side, settings.vlm_max_side))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        b64 = base64.b64encode(buf.getvalue()).decode()
        if self.nuextract:
            messages = [
                {"role": "template", "content": json.dumps(nuextract_template(options))},
                {"role": "instructions", "content": f"{MERCHANT_RULE} {DATE_RULE} {TOTAL_RULE}"},
                {"role": "user", "content": "", "images": [b64]},
            ]
            fmt = None
        else:
            messages = [{"role": "user", "content": generic_prompt(options), "images": [b64]}]
            fmt = json_schema(options)
        payload = {
            "model": self.model, "messages": messages, "stream": False, "think": False,
            "keep_alive": settings.vlm_keep_alive,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2048},
        }
        if fmt:
            payload["format"] = fmt
        return payload

    def _chat(self, payload: Dict[str, Any], timeout: float) -> str:
        try:
            r = requests.post(f"{self.host}/api/chat", json=payload, timeout=timeout)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Vision model API error: {e}") from e
        content = r.json().get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Empty answer from the vision model")
        return content

    async def health_check(self) -> Dict[str, Any]:
        try:
            r = await asyncio.to_thread(requests.get, f"{self.host}/api/tags", timeout=5)
            r.raise_for_status()
            names = [m.get("name") for m in r.json().get("models", [])]
            return {"status": "connected", "backend": "Ollama vision", "model": self.model,
                    "model_available": self.model in names, "host": self.host}
        except Exception as e:
            return {"status": "error", "backend": "Ollama vision", "model": self.model, "error": str(e)[:200]}
