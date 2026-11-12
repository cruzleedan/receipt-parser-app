"""WORK-0008: the local vision-model backend."""

import io
import math
import json
import time

import httpx
import pytest
from PIL import Image

import src.main as main
from src.config import settings
from src.models import ExtractionOptions
from src.utils import normalise_date
from src.vlm_service import VisionLLMService, field_confidence, generic_prompt, json_schema, keep_alive, nuextract_template, to_receipt
from src.currency import normalise_currency


@pytest.mark.parametrize("raw, iso", [
    ("07/26/24", "2024-07-26"),          # month first, two-digit year (Philippine receipts)
    ("08-27-2026", "2026-08-27"),
    ("2024-07-26", "2024-07-26"),        # year first kept
    ("2024/7/5", "2024-07-05"),
    ("26/07/2024", "2024-07-26"),        # first number cannot be a month: day first
    ("Jul 26, 2024", "2024-07-26"),
    ("12 Mar 2025", "2025-03-12"),
    ("DATE: 05/16/21 10:23", "2021-05-16"),
    ("02/30/2024", None),                # impossible date
    ("", None), (None, None), ("10:23 AM", None),
])
def test_dates_are_read_month_first(raw, iso):
    assert normalise_date(raw) == iso


def test_answer_is_cleaned_into_receipt_data():
    r = to_receipt({
        "merchant_name": "  SM Supermarket ", "date": "07/26/24", "total": 7112,
        "subtotal": "n/a", "tax": 0,
        "items": [
            {"name": "Rice 5kg", "quantity": 1, "unit_price": 300, "total_price": 300},
            {"name": "Beef", "quantity": 0.5, "unit_price": None, "total_price": 250.5},   # weight -> 1
            {"name": "", "quantity": 1, "total_price": 10},                                 # no name: dropped
            {"name": "Free bag", "quantity": 1, "total_price": None},                       # no price: dropped
        ],
    })
    assert r.merchant_name == "SM Supermarket"
    assert r.date == "2024-07-26"
    assert r.total == 7112.0 and r.subtotal is None and r.tax == 0
    assert [(i.name, i.quantity, i.total_price) for i in r.items] == [("Rice 5kg", 1, 300.0), ("Beef", 1, 250.5)]


@pytest.mark.parametrize("bad", [{"merchant_name": "X", "total": None}, {"total": "12.00"}, [], "x"])
def test_an_answer_without_a_numeric_total_is_rejected(bad):
    with pytest.raises(ValueError):
        to_receipt(bad)


def test_every_schema_key_is_required_and_follows_the_options():
    schema = json_schema(ExtractionOptions())
    assert set(schema["required"]) == set(schema["properties"])
    assert {"merchant_name", "date", "total", "items", "subtotal", "tax", "currency"} <= set(schema["properties"])
    assert "cashier" not in schema["properties"]
    with_cashier = json_schema(ExtractionOptions(cashier=True, payment_method=True))
    assert {"cashier", "payment_method", "card_last_4"} <= set(with_cashier["properties"])
    assert nuextract_template(ExtractionOptions())["date"] == "verbatim-string"


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format="PNG")
    return buf.getvalue()


class StubOCR:
    def extract_text(self, image):
        raise AssertionError("the fallback should not run")

    async def health_check(self):
        return {"status": "ready"}


class StubLLM:
    async def health_check(self):
        return {"status": "connected"}


@pytest.fixture
def vlm_app(monkeypatch):
    monkeypatch.setattr(settings, "parser_backend", "vlm_ollama")
    monkeypatch.setattr(settings, "parse_deadline_seconds", 5)
    monkeypatch.setattr(settings, "vlm_fallback_reserve_seconds", 1)
    monkeypatch.setattr(main, "ocr_service", StubOCR())
    monkeypatch.setattr(main, "llm_service", StubLLM())
    svc = VisionLLMService(host="http://stub", model="qwen3.5:4b")
    monkeypatch.setattr(main, "vlm_service", svc)
    return svc


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")


async def test_the_vision_model_answers_the_parse(vlm_app, monkeypatch):
    sent = {}

    def chat(payload, timeout):
        sent.update(payload=payload, timeout=timeout)
        return json.dumps({"merchant_name": "Mercury Drug", "date": "08/29/24", "total": 262.5, "items": []})

    monkeypatch.setattr(vlm_app, "_chat", chat)
    async with _client() as client:
        r = await client.post("/parse", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert (body["merchant_name"], body["date"], body["total"]) == ("Mercury Drug", "2024-08-29", 262.5)
    assert body["processing_metadata"]["ocr_time_ms"] == 0.0
    assert sent["payload"]["format"]["required"] and sent["payload"]["think"] is False
    assert sent["timeout"] <= 4   # bounded by the parse deadline minus the fallback reserve


async def test_a_failed_vision_answer_falls_back_to_the_local_pipeline(vlm_app, monkeypatch):
    monkeypatch.setattr(vlm_app, "_chat", lambda payload, timeout: json.dumps({"total": None}))
    called = []

    async def fallback(image, options, start_time, deadline=None):
        called.append(True)
        return main.JSONResponse(status_code=422, content={"error": "No text detected"})

    monkeypatch.setattr(main, "_parse_with_paddleocr_ollama", fallback)
    async with _client() as client:
        r = await client.post("/parse", files={"file": ("r.png", _png(), "image/png")})
    assert called and r.status_code == 422


def test_nuextract_is_prompted_with_its_own_roles():
    svc = VisionLLMService(host="http://stub", model="numind/nuextract3:Q4_K_M")
    payload = svc._payload(Image.new("RGB", (10, 10)), ExtractionOptions())
    roles = [m["role"] for m in payload["messages"]]
    assert roles == ["template", "instructions", "user"] and "format" not in payload
    assert json.loads(payload["messages"][0]["content"])["total"] == "number"


async def test_health_reports_the_vision_model(vlm_app, monkeypatch):
    async def ok():
        return {"status": "connected", "model_available": True}
    monkeypatch.setattr(vlm_app, "health_check", ok)
    async with _client() as client:
        r = await client.get("/health")
    assert r.json()["services"]["vlm"]["model_available"] is True and r.json()["status"] == "healthy"


def test_keep_alive_numbers_are_sent_as_numbers():
    # Production regression (2026-11-12): Ollama rejected keep_alive "-1" with 400.
    assert keep_alive("-1") == -1 and keep_alive("0") == 0 and keep_alive("30m") == "30m"
    svc = VisionLLMService(host="http://stub", model="qwen3.5:4b")
    import src.vlm_service as vs
    old = vs.settings.vlm_keep_alive
    try:
        vs.settings.vlm_keep_alive = "-1"
        assert svc._payload(Image.new("RGB", (10, 10)), ExtractionOptions())["keep_alive"] == -1
    finally:
        vs.settings.vlm_keep_alive = old


# WORK-0014: the currency comes back as an ISO code, or null when missing, unknown or ambiguous.
@pytest.mark.parametrize("raw, code", [
    ("PHP", "PHP"), ("php", "PHP"), ("₱", "PHP"), ("P", "PHP"), (" Peso ", "PHP"),
    ("USD", "USD"), ("US$", "USD"), ("€", "EUR"), ("jpy", "JPY"), ("S$", "SGD"),
    ("$", None), ("¥", None), ("XYZ", None), ("", None), (None, None), (12, None),
])
def test_currency_is_cleaned_to_an_iso_code(raw, code):
    assert normalise_currency(raw) == code


def test_the_currency_reaches_the_receipt_and_is_asked_for():
    assert to_receipt({"merchant_name": "Jollibee", "total": 99, "currency": "₱"}).currency == "PHP"
    assert to_receipt({"merchant_name": "Diner", "total": 9, "currency": "$"}).currency is None
    assert to_receipt({"merchant_name": "Old answer", "total": 9}).currency is None
    assert "ISO 4217" in generic_prompt(ExtractionOptions())


# WORK-0016: the lowest digit probability inside each field's value.
def test_field_confidence_takes_the_least_sure_digit_of_each_field():
    lp = math.log
    tokens = [('{"', lp(0.9)), ("date", lp(1)), ('": "', lp(1)), ("0", lp(0.99)), ("8", lp(0.42)), ("/29/24", lp(0.97)),
              ('", "', lp(1)), ("total", lp(1)), ('": ', lp(0.1)), ("262", lp(0.95)), (".", lp(0.5)), ("50", lp(0.88)), ("}", lp(1))]
    conf = field_confidence(tokens)
    assert conf == {"date": 0.42, "total": 0.88}, "the '.' and the punctuation around values do not count"
    assert field_confidence(None) is None and field_confidence([]) is None
    assert field_confidence([('{"total": null}', 0.0)]) == {"date": None, "total": None}


async def test_the_parse_reports_field_confidence(vlm_app, monkeypatch):
    sent = {}
    answer = '{"merchant_name": "A", "date": "08/29/24", "total": 9}'

    def chat(payload, timeout):
        sent.update(payload=payload)
        parts = ['{"merchant_name": "A", "date": "', "08/29/24", '", "total": ', "9", "}"]
        assert "".join(parts) == answer
        return answer, list(zip(parts, map(math.log, [1.0, 0.6, 1.0, 0.95, 1.0])))

    monkeypatch.setattr(vlm_app, "_chat", chat)
    async with _client() as client:
        r = await client.post("/parse", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 200 and sent["payload"]["logprobs"] is True
    assert r.json()["field_confidence"] == {"date": 0.6, "total": 0.95}
