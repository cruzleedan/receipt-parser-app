"""Behavioral regression coverage for WORK-0017 through WORK-0031."""

import asyncio
import importlib.util
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from PIL import Image

import src.main as main
from src.config import settings
from src.models import ExtractionOptions, ReceiptData, ReceiptItem
from src.vlm_service import VisionLLMService, to_receipt
from src.llm_service import OllamaLLMService
from src.gemini_service import GeminiReceiptService
from src.ocr_service import ReceiptOCRService
from src.utils import load_image_from_bytes
from src.workers import BoundedWorker, CapacityError
from src.http_client import model_available


def png(size=(40, 40)):
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, format="PNG")
    return buf.getvalue()


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")


class ReadyOCR:
    def extract_text(self, image):
        raise AssertionError("Unexpected OCR fallback")

    async def health_check(self):
        return {"status": "ready"}


class ReadyLLM:
    async def health_check(self):
        return {"status": "connected", "model_available": True}


class ReadyVLM:
    async def parse_receipt(self, image, **kwargs):
        return ReceiptData(merchant_name="Example", date="2024-07-26", total=80, currency="₱")

    async def health_check(self):
        return {"status": "connected", "model_available": True}


@pytest.fixture
def ready(monkeypatch):
    monkeypatch.setattr(settings, "parser_backend", "vlm_ollama")
    monkeypatch.setattr(settings, "parse_deadline_seconds", 1)
    monkeypatch.setattr(settings, "batch_deadline_seconds", 1)
    monkeypatch.setattr(main, "ocr_service", ReadyOCR())
    monkeypatch.setattr(main, "llm_service", ReadyLLM())
    monkeypatch.setattr(main, "vlm_service", ReadyVLM())


async def test_batch_matches_single_backend_and_preserves_partial_results(ready):
    async with client() as c:
        single = await c.post("/parse?items=false", files={"file": ("x.png", png(), "image/png")})
        batch = await c.post("/parse-batch?items=false", files=[
            ("files", ("x.png", png(), "image/png")),
            ("files", ("bad.png", b"corrupt", "image/png")),
            ("files", ("bad.pdf", b"pdf", "application/pdf")),
        ])
    assert single.status_code == batch.status_code == 200
    assert single.json()["processing_metadata"]["backend"] == "vlm_ollama"
    body = batch.json()
    assert (body["successful"], body["failed"]) == (1, 2)
    assert body["results"][0]["data"]["total"] == single.json()["total"]
    assert body["results"][0]["data"]["currency"] == "PHP"


async def test_batch_deadline_bounds_slow_receipt_and_skips_rest(ready, monkeypatch):
    calls = []
    async def slow(*args, **kwargs):
        calls.append(kwargs)
        await asyncio.sleep(5)
    monkeypatch.setattr(main.vlm_service, "parse_receipt", slow)
    monkeypatch.setattr(settings, "batch_deadline_seconds", .08)
    async with client() as c:
        started = time.monotonic()
        r = await c.post("/parse-batch", files=[("files", (f"{i}.png", png(), "image/png")) for i in range(3)])
    assert time.monotonic() - started < .6
    assert len(calls) == 1
    assert r.json()["failed"] == 3
    assert "not processed" in r.json()["results"][2]["error"]


async def test_batch_uses_same_fallback(ready, monkeypatch):
    async def fail(*args, **kwargs):
        raise ValueError("invalid primary")
    calls = []
    async def fallback(image, options, started, deadline):
        calls.append((options.items, deadline))
        return main.ReceiptResponse(merchant_name="Fallback", total=12, items=[],
            processing_metadata=main.ProcessingMetadata(ocr_time_ms=1, llm_time_ms=1, total_time_ms=2, ocr_confidence=.9))
    monkeypatch.setattr(main.vlm_service, "parse_receipt", fail)
    monkeypatch.setattr(main, "_parse_with_paddleocr_ollama", fallback)
    async with client() as c:
        r = await c.post("/parse-batch?items=false", files={"files": ("x.png", png(), "image/png")})
    assert r.json()["results"][0]["data"]["merchant_name"] == "Fallback"
    assert calls[0][0] is False


async def test_admission_refuses_parallel_parse_without_blocking_health(ready, monkeypatch):
    entered, finish = asyncio.Event(), asyncio.Event()
    async def waiting(*args, **kwargs):
        entered.set()
        await finish.wait()
        return ReceiptData(merchant_name="Test", total=1)
    monkeypatch.setattr(main.vlm_service, "parse_receipt", waiting)
    async with client() as c:
        first = asyncio.create_task(c.post("/parse", files={"file": ("x.png", png(), "image/png")}))
        await entered.wait()
        r = await c.post("/parse", files={"file": ("x.png", png(), "image/png")})
        assert r.status_code == 503 and r.headers["retry-after"] == "2"
        assert (await c.get("/ready")).status_code == 200
        finish.set()
        assert (await first).status_code == 200


async def test_cancelled_worker_holds_slot_until_actual_completion():
    worker = BoundedWorker()
    entered, finish = threading.Event(), threading.Event()
    def blocked():
        entered.set()
        finish.wait(2)
        return 42
    task = asyncio.create_task(worker.run(blocked))
    while not entered.is_set():
        await asyncio.sleep(.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    try:
        with pytest.raises(CapacityError):
            await worker.run(lambda: 7)
    finally:
        finish.set()
    for _ in range(100):
        try:
            assert await worker.run(lambda: 7) == 7
            break
        except CapacityError:
            await asyncio.sleep(.005)
    else:
        pytest.fail("Worker capacity did not recover")
    worker._executor.shutdown()


async def test_real_health_http_yields_and_requires_exact_tag(monkeypatch):
    import src.http_client as transport
    original = httpx.AsyncClient
    entered = asyncio.Event()
    async def handler(request):
        entered.set()
        await asyncio.sleep(.1)
        return httpx.Response(200, json={"models": [{"name": "llama:other"}]})
    monkeypatch.setattr(transport.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler)))
    svc = OllamaLLMService(host="http://stub", model="llama:required")
    task = asyncio.create_task(svc.health_check())
    await entered.wait()
    await asyncio.sleep(.01)
    assert not task.done()
    assert (await task)["model_available"] is False
    assert model_available("llama", ["llama:latest"])
    assert not model_available("llama", ["llama:other"])


async def test_degraded_health_is_not_ready(ready, monkeypatch):
    async def absent():
        return {"status": "connected", "model_available": False}
    monkeypatch.setattr(main.llm_service, "health_check", absent)
    async with client() as c:
        assert (await c.get("/health")).json()["status"] == "degraded"
        assert (await c.get("/ready")).status_code == 503


async def test_network_call_is_cancelled_at_wall_clock_budget(monkeypatch):
    import src.http_client as transport
    original = httpx.AsyncClient
    cancelled = asyncio.Event()
    async def handler(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()
    monkeypatch.setattr(transport.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler)))
    with pytest.raises(TimeoutError):
        await transport.post_json("http://stub", {}, .03)
    assert cancelled.is_set()


async def test_byte_and_pixel_limits_are_handled(ready, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 50)
    async with client() as c:
        assert (await c.post("/parse", files={"file": ("x.png", png(), "image/png")})).status_code == 413
    monkeypatch.setattr(settings, "max_upload_bytes", 100_000)
    monkeypatch.setattr(settings, "max_image_pixels", 100)
    async with client() as c:
        assert (await c.post("/parse", files={"file": ("x.png", png(), "image/png")})).status_code == 413


async def test_streaming_ingress_limit_applies_before_multipart_parsing(ready, monkeypatch):
    monkeypatch.setattr(settings, "max_request_bytes", 1024)
    async def chunks():
        yield b"--x\r\nContent-Disposition: form-data; name=\"file\"; filename=\"r.png\"\r\nContent-Type: image/png\r\n\r\n"
        yield b"x" * 2000
        yield b"\r\n--x--\r\n"
    async with client() as c:
        r = await c.post("/parse", content=chunks(), headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413


@pytest.mark.parametrize("orientation,size", [(1,(40,20)), (3,(40,20)), (6,(20,40)), (8,(20,40))])
def test_exif_orientation_consumed_once(orientation, size):
    image = Image.new("RGB", (40,20))
    image.paste((255,0,0),(0,0,10,10))
    exif = Image.Exif(); exif[274] = orientation
    buf = io.BytesIO(); image.save(buf, format="JPEG", exif=exif)
    result = load_image_from_bytes(buf.getvalue())
    assert result.size == size and result.getexif().get(274) in (None, 1)
    marker = {1:(5,5),3:(34,14),6:(14,5),8:(5,34)}[orientation]
    red,green,blue = result.getpixel(marker)
    assert red > 200 and green < 50 and blue < 50


async def test_ocr_footer_is_retained_or_explicitly_rejected(monkeypatch):
    service = OllamaLLMService(host="http://stub")
    seen = []
    async def call(prompt, *args):
        seen.append(prompt)
        return '{"merchant_name":"Store","total":123.45,"items":[]}'
    monkeypatch.setattr(service, "_call_ollama", call)
    await service.parse_receipt("item 1.00\n" * 500 + "TOTAL 123.45")
    assert "TOTAL 123.45" in seen[0]
    with pytest.raises(ValueError, match="context budget"):
        await service.parse_receipt("item" * 10_000)
    assert len(seen) == 1


@pytest.mark.parametrize("value", [True,False,float("inf"),float("-inf"),float("nan")])
def test_bad_money_rejected_at_shared_boundaries(value):
    with pytest.raises(ValueError):
        ReceiptData(merchant_name="X", total=value)
    with pytest.raises(ValueError):
        ReceiptItem(name="X",total_price=1,unit_price=value)
    with pytest.raises(ValueError):
        to_receipt({"merchant_name":"X","total":1,"items":[{"name":"X","total_price":value}]})


@pytest.mark.parametrize("raw,expected", [("₱","PHP"),("US$","USD"),("$",None),("XYZ",None),(None,None)])
def test_all_backends_share_currency_and_long_item_rules(raw, expected):
    answer = {"merchant_name":"X","total":12,"currency":raw,
              "items":[{"name":f"Item {i}","total_price":1} for i in range(12)]}
    text = OllamaLLMService()
    vision = to_receipt(answer)
    gemini = GeminiReceiptService(api_key="stub")
    for receipt in (vision,text._parse_response(json.dumps(answer)),gemini._parse_response(json.dumps(answer))):
        assert receipt.currency == expected and len(receipt.items) == 12
    for prompt in (text._build_prompt("TOTAL 80 CASH 100 CHANGE 20"),gemini._build_prompt()):
        assert "cash tendered" in prompt and "currency" in prompt
        assert "Up to 10" not in prompt and "largest total" not in prompt


async def test_text_inference_honors_settings_independently_of_ocr(monkeypatch):
    import src.llm_service as module
    seen = []
    async def post(url, payload, timeout):
        seen.append(payload)
        return {"response":'{"merchant_name":"X","total":1}',"done_reason":"stop"}
    monkeypatch.setattr(module, "post_json", post)
    monkeypatch.setattr(settings, "ollama_num_predict", 3072)
    monkeypatch.setattr(settings, "ollama_top_p", .5)
    monkeypatch.setattr(settings, "ollama_temperature", .2)
    monkeypatch.setattr(settings, "ocr_use_gpu", False)
    await OllamaLLMService()._call_ollama("test")
    assert "num_gpu" not in seen[0]["options"]
    assert seen[0]["options"]["num_predict"] == 3072
    assert seen[0]["options"]["top_p"] == .5
    assert seen[0]["options"]["temperature"] == .2


async def test_truncated_valid_json_is_not_accepted(monkeypatch):
    async def truncated(*args):
        return {"response":'{"merchant_name":"X","total":1}',
                "message":{"content":'{"merchant_name":"X","total":1}'},"done_reason":"length"}
    import src.llm_service as text
    import src.vlm_service as vision
    monkeypatch.setattr(text, "post_json", truncated)
    monkeypatch.setattr(vision, "post_json", truncated)
    with pytest.raises(ValueError, match="incomplete"):
        await OllamaLLMService()._call_ollama("test")
    with pytest.raises(ValueError, match="incomplete"):
        await VisionLLMService()._chat({}, 1)


def test_ocr_uses_recognition_polygons_and_explicit_device(monkeypatch):
    import src.ocr_service as module
    import numpy as np
    captured = {}
    class Engine:
        def __init__(self, **kwargs): captured.update(kwargs)
        def predict(self,image):
            return [{"rec_texts":["TOTAL 1"],"rec_scores":[.9],
                     "dt_polys":np.array([[[0,0]],[[10,10]]]),"rec_polys":[np.array([[10,10]])]}]
    monkeypatch.setattr(module,"PaddleOCR",Engine)
    service = ReceiptOCRService(use_gpu=False)
    assert captured["device"] == "cpu"
    result=service.extract_text(Image.new("RGB",(40,40)))
    assert result.boxes[0]["points"] == [[10.,10.]]
    assert json.loads(result.model_dump_json())["boxes"][0]["points"] == [[10.,10.]]
    with pytest.raises(ValueError,match="misaligned"):
        service._serialize_boxes(np.zeros((2,4,2)),["one"],[.9])


def load_bench(name):
    path = Path(__file__).resolve().parents[1] / "bench" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_benchmark_answers_count_as_failures(tmp_path,capsys):
    score = load_bench("score_labels")
    labels = {f"r{i:03d}":{"merchant":"X","date":"2024-07-26","total":"1"} for i in range(2)}
    label_path=tmp_path/"labels.json"; label_path.write_text(json.dumps(labels))
    run=tmp_path/"run.jsonl"
    record={"id":"r000","raw":json.dumps({"merchant_name":"X","date":"2024-07-26","total":1})}
    run.write_text(json.dumps(record)+"\n")
    score.main(label_path,[run])
    output=capsys.readouterr().out
    assert "| 2 | 1/2 | 50% (1)" in output and output.rstrip().endswith("| 1 |")
    run.write_text((json.dumps(record)+"\n")*2)
    with pytest.raises(ValueError,match="Duplicate"):
        score.main(label_path,[run])


def test_concurrent_label_transactions_preserve_updates_and_old_file(tmp_path,monkeypatch):
    labels=load_bench("label_server")
    path=tmp_path/"labels.json"
    monkeypatch.setattr(labels,"LABELS",path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda i: labels.save_label(f"r{i:03d}",{"total":i}),range(40)))
    assert len(json.loads(path.read_text())) == 40
    before=path.read_bytes()
    def fail(*args): raise OSError("disk full")
    monkeypatch.setattr(labels.os,"replace",fail)
    with pytest.raises(OSError): labels.save_label("r999",{})
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


async def test_preprocessing_uses_deadline_and_busy_slot_survives(ready, monkeypatch):
    worker = BoundedWorker()
    entered, finish = threading.Event(), threading.Event()
    def slow_decode(data):
        entered.set()
        finish.wait(2)
        return Image.new("RGB",(40,40))
    monkeypatch.setattr(main,"image_worker",worker)
    monkeypatch.setattr(main,"load_image_from_bytes",slow_decode)
    monkeypatch.setattr(settings,"parse_deadline_seconds",.05)
    try:
        async with client() as c:
            r = await c.post("/parse",files={"file":("x.png",png(),"image/png")})
            assert entered.is_set() and r.status_code == 504
            second = await c.post("/parse",files={"file":("x.png",png(),"image/png")})
            assert second.status_code == 503
    finally:
        finish.set()
        await asyncio.to_thread(worker._executor.shutdown)


async def test_ingress_slow_body_gets_handled_timeout(ready,monkeypatch):
    monkeypatch.setattr(settings,"ingress_timeout_seconds",.03)
    async def slow_body():
        await asyncio.sleep(.2)
        yield b"--x--\r\n"
    async with client() as c:
        r=await c.post("/parse",content=slow_body(),headers={"Content-Type":"multipart/form-data; boundary=x"})
    assert r.status_code == 408


@pytest.mark.parametrize("amount",[0,-12.5])
def test_zero_and_refunds_remain_valid(amount):
    assert to_receipt({"merchant_name":"X","total":amount}).total == amount


async def test_gemini_uses_cancellable_sdk_coroutine(monkeypatch):
    from types import SimpleNamespace
    service=GeminiReceiptService(api_key="stub")
    cancelled=asyncio.Event()
    async def generate(**kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()
    monkeypatch.setattr(service,"client",SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(service._call_gemini("prompt",b"png"),.03)
    assert cancelled.is_set()


async def test_failed_and_slow_dependencies_are_not_ready(ready,monkeypatch):
    async def broken():
        raise httpx.ConnectError("Ollama unavailable")
    monkeypatch.setattr(main.llm_service,"health_check",broken)
    async with client() as c:
        assert (await c.get("/ready")).status_code == 503
    async def slow():
        await asyncio.sleep(10)
    monkeypatch.setattr(main.llm_service,"health_check",slow)
    monkeypatch.setattr(settings,"health_timeout_seconds",.02)
    async with client() as c:
        started=time.monotonic()
        assert (await c.get("/ready")).status_code == 503
        assert time.monotonic()-started < .3


def test_benchmark_amounts_preserve_refunds_and_reject_nonfinite():
    module=load_bench("consistency")
    assert module.num("PHP -1,234.50") == -1234.5
    assert module.num("(12.50)") == -12.5
    assert module.num(True) is None
    assert module.num(float("inf")) is None
    assert module.num(float("nan")) is None
