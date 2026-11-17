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
import math
import re
import base64
import io
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from src.config import settings
from src.models import ExtractionOptions, ReceiptData
from src.utils import normalise_date
from src.currency import normalise_currency

logger = logging.getLogger(__name__)

from src.extraction import (
    FIELDS, TOTAL_RULE, MERCHANT_RULE, DATE_RULE, CURRENCY_RULE,
    json_schema, nuextract_template, generic_prompt,
)
from src.workers import image_worker
from src.http_client import post_json, get_json, model_available, require_complete

def to_receipt(data: Dict[str, Any]) -> ReceiptData:
    """Clean the model's answer into ReceiptData; raises ValueError when unusable."""
    if not isinstance(data, dict):
        raise ValueError("answer is not a JSON object")
    def check_money(value):
        if isinstance(value, bool) or isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError("Invalid monetary amount")

    for key in ("total", "subtotal", "tax", "tip", "discount"):
        check_money(data.get(key))
    for item in data.get("items") or []:
        if isinstance(item, dict):
            check_money(item.get("unit_price"))
            check_money(item.get("total_price"))
    total = data.get("total")
    if not isinstance(total, (int, float)):
        raise ValueError("no total")
    items = []
    warnings = []
    for it in data.get("items") or []:
        if not isinstance(it, dict) or not it.get("name") or not isinstance(it.get("total_price"), (int, float)):
            warnings.append("A line item could not be read completely")
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
    clean["currency"] = normalise_currency(data.get("currency"))
    for k in ("subtotal", "tax", "tip", "discount"):
        if k in clean and not isinstance(clean[k], (int, float)):
            clean[k] = None
    for k in ("merchant_address", "merchant_phone", "time", "payment_method", "card_last_4", "receipt_number", "cashier"):
        if k in clean and clean[k] is not None:
            clean[k] = str(clean[k])[:200]
    clean["items"] = items
    clean["extraction_warnings"] = sorted(set(warnings))
    return ReceiptData(**clean)


# WORK-0016 (spike WORK-0015): the model's own doubt about a field is the lowest probability of any digit
# it wrote inside that field's value. On the owner's labelled receipts this separates wrong totals and dates.
CONFIDENCE_FIELDS = {"date": r'"date"\s*:\s*"([^"]*)"', "total": r'"total"\s*:\s*(-?[\d.,]+)'}


def field_confidence(tokens: Optional[List[Tuple[str, float]]]) -> Optional[Dict[str, Optional[float]]]:
    """{field: lowest digit probability (0..1), or None when the field has no digits}; None without tokens."""
    if not tokens:
        return None
    text, starts = "", []
    for tok, _ in tokens:
        starts.append(len(text))
        text += tok
    out: Dict[str, Optional[float]] = {}
    for field, pattern in CONFIDENCE_FIELDS.items():
        m = re.search(pattern, text)
        if not m:
            out[field] = None
            continue
        a, b = m.span(1)
        probs = [math.exp(lp) for (tok, lp), s in zip(tokens, starts) if s < b and s + len(tok) > a and re.search(r"\d", tok)]
        out[field] = round(min(probs), 4) if probs else None
    return out


def keep_alive(value: str):
    """Ollama takes a duration ("30m") or a number of seconds (-1 = stay loaded), never "-1"."""
    v = str(value).strip()
    return int(v) if v.lstrip("-").isdigit() else v


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
        # Preprocessing is charged to the primary budget and runs off the event loop.
        call_deadline = min(
            time.monotonic() + settings.vlm_timeout,
            deadline - reserve_seconds if deadline is not None else float("inf"),
        )
        if call_deadline - time.monotonic() < 1:
            raise TimeoutError("parse deadline reached before the vision-model call")
        started = time.monotonic()
        async with asyncio.timeout_at(call_deadline):
            payload = await image_worker.run(self._payload, image, options)
            answer = await self._chat(payload, call_deadline - time.monotonic())
        content, tokens = (answer, None) if isinstance(answer, str) else answer
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"vision model answer is not JSON: {e}") from e
        receipt = to_receipt(data)
        receipt.field_confidence = field_confidence(tokens)
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
            "keep_alive": keep_alive(settings.vlm_keep_alive),
            "options": {"temperature": 0, "num_ctx": settings.vlm_num_ctx, "num_predict": settings.vlm_num_predict},
        }
        if fmt:
            payload["format"] = fmt
            payload["logprobs"] = True  # WORK-0016: per-token probabilities for field_confidence
        return payload

    async def _chat(self, payload: Dict[str, Any], timeout: float):
        body = await post_json(f"{self.host}/api/chat", payload, timeout)
        require_complete(body)
        content = body.get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Empty answer from the vision model")
        tokens = [(t.get("token", ""), t.get("logprob", 0.0)) for t in body.get("logprobs") or []]
        logger.info("VLM timings load_ms=%.0f prompt_ms=%.0f eval_ms=%.0f output_tokens=%s",
                    body.get("load_duration", 0) / 1e6, body.get("prompt_eval_duration", 0) / 1e6,
                    body.get("eval_duration", 0) / 1e6, body.get("eval_count"))
        return (content, tokens) if tokens else content

    async def health_check(self) -> Dict[str, Any]:
        try:
            body = await get_json(f"{self.host}/api/tags")
            names = [m.get("name") for m in body.get("models", [])]
            return {"status": "connected", "backend": "Ollama vision", "model": self.model,
                    "model_available": model_available(self.model, names), "host": self.host}
        except Exception as e:
            return {"status": "error", "backend": "Ollama vision", "model": self.model, "error": str(e)[:200]}
