"""WORK-0005: one deadline per parse, Gemini bounded, blocking work off the event loop."""

import asyncio
import io
import time

import httpx
import pytest
from PIL import Image

import src.main as main  # noqa: E402
from src.config import settings
from src.gemini_service import GeminiReceiptService
from src.llm_service import OllamaLLMService
from src.models import OCRResult


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format="PNG")
    return buf.getvalue()


class SlowOCR:
    def __init__(self, seconds: float):
        self.seconds = seconds

    def extract_text(self, image):
        time.sleep(self.seconds)  # blocking, like PaddleOCR
        return OCRResult(full_text="TOTAL 1.00", confidence=0.9)

    async def health_check(self):
        return {"status": "ready", "backend": "stub", "gpu_enabled": False, "language": "en"}


class StubLLM:
    async def parse_receipt(self, *args, **kwargs):
        await asyncio.sleep(10)

    async def health_check(self):
        return {"status": "connected", "backend": "stub", "model": "stub", "model_available": True, "host": "stub"}


@pytest.fixture
def stubbed(monkeypatch):
    monkeypatch.setattr(settings, "parser_backend", "paddleocr_ollama")
    monkeypatch.setattr(main, "gemini_service", None)
    monkeypatch.setattr(main, "llm_service", StubLLM())
    return monkeypatch


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")


async def test_parse_past_its_deadline_answers_504(stubbed):
    stubbed.setattr(settings, "parse_deadline_seconds", 0.5)
    stubbed.setattr(main, "ocr_service", SlowOCR(0.1))
    async with _client() as client:
        started = time.monotonic()
        r = await client.post("/parse", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 504
    assert r.json()["error"] == "Parse deadline exceeded"
    assert time.monotonic() - started < 2


async def test_health_answers_while_ocr_runs(stubbed):
    stubbed.setattr(settings, "parse_deadline_seconds", 3)
    stubbed.setattr(main, "ocr_service", SlowOCR(1.5))
    async with _client() as client:
        parse = asyncio.create_task(client.post("/parse", files={"file": ("r.png", _png(), "image/png")}))
        await asyncio.sleep(0.2)
        started = time.monotonic()
        health = await client.get("/health")
        assert health.status_code == 200
        assert time.monotonic() - started < 1, "health waited for the blocking OCR"
        await parse


def _gemini(monkeypatch, call):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    service = GeminiReceiptService(api_key="test-key", model="stub")
    monkeypatch.setattr(service, "_call_gemini", call)
    return service


async def test_gemini_is_skipped_when_only_the_fallback_reserve_is_left(monkeypatch):
    calls = []
    service = _gemini(monkeypatch, lambda *a: calls.append(a) or "{}")
    with pytest.raises(RuntimeError, match="skipped"):
        await service.parse_receipt(Image.new("RGB", (10, 10)), deadline=time.monotonic() + 10, reserve_seconds=9.5)
    assert calls == []


async def test_each_gemini_attempt_is_bounded(monkeypatch):
    service = _gemini(monkeypatch, lambda *a: time.sleep(3) or "{}")
    service.timeout_seconds = 0.3
    started = time.monotonic()
    with pytest.raises(RuntimeError):
        await service.parse_receipt(Image.new("RGB", (10, 10)), deadline=time.monotonic() + 60)
    assert time.monotonic() - started < 2.5  # two 0.3 s attempts and the 1 s pause, not 6 s


async def test_ollama_is_not_called_after_the_deadline(monkeypatch):
    service = OllamaLLMService(host="http://stub", model="stub")
    called = []
    monkeypatch.setattr(service, "_call_ollama", lambda *a: called.append(a) or "{}")
    with pytest.raises(TimeoutError):
        await service.parse_receipt("TOTAL 1.00", deadline=time.monotonic() - 1)
    assert called == []


def test_gemini_timeout_reaches_the_client(monkeypatch):
    monkeypatch.setattr(settings, "gemini_timeout", 7)
    service = GeminiReceiptService(api_key="test-key", model="stub")
    assert service.timeout_seconds == 7
