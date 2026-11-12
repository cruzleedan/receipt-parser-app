"""WORK-0012: checks against a running parser with its real model, OCR and network.

Skipped unless PARSER_URL is set. Run before a deploy (against a candidate container) and
after it (against receipt-parser-app) with scripts/verify-deployment.sh. Uses only the
public sample receipts in receipts/, never user receipts.
"""

import io
import os
from pathlib import Path

import httpx
import pytest
from PIL import Image

URL = os.environ.get("PARSER_URL")
SAMPLES = Path(os.environ.get("SAMPLE_DIR", Path(__file__).resolve().parent.parent / "receipts"))
EXPECTED_BACKEND = os.environ.get("EXPECTED_BACKEND", "vlm_ollama")

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not URL, reason="PARSER_URL not set")]


def client():
    return httpx.Client(base_url=URL, timeout=100)


def test_health_reports_the_intended_backend_ready():
    body = client().get("/health").json()
    assert body["status"] == "healthy", body
    if EXPECTED_BACKEND == "vlm_ollama":
        vlm = body["services"]["vlm"]
        assert vlm["status"] == "connected" and vlm["model_available"], vlm


def test_the_sample_receipt_is_read_by_the_intended_backend():
    with client() as c:
        r = c.post("/parse", files={"file": ("small-receipt.png", (SAMPLES / "small-receipt.png").read_bytes(), "image/png")})
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    meta = body["processing_metadata"]
    if EXPECTED_BACKEND == "vlm_ollama":
        # The vision path reports no OCR time; a fallback reports PaddleOCR's. This is the check
        # that the keep_alive and Gemini-v1 regressions would have failed (WORK-0012).
        assert meta["ocr_time_ms"] == 0.0, f"answered by the fallback, not the vision model: {meta}"
    assert abs(body["total"] - 24.10) < 0.01, body
    assert len(body["items"]) >= 3, body["items"]
    assert meta["total_time_ms"] < 70_000


def test_a_non_image_is_refused():
    with client() as c:
        r = c.post("/parse", files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 400


def test_a_blank_image_ends_in_a_handled_answer():
    buf = io.BytesIO()
    Image.new("RGB", (600, 900), "white").save(buf, format="PNG")
    with client() as c:
        r = c.post("/parse", files={"file": ("blank.png", buf.getvalue(), "image/png")})
    # No receipt: either the model answers something with a total, or the fallback finds no
    # text (422) or the deadline passes (504). Never an unhandled 500.
    assert r.status_code in (200, 422, 504), r.text[:300]
