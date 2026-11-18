"""Pure timing-replay regressions; no model, network or receipt fixture required."""
from bench.fallback_schedule import replay, summary
import pytest


def stage(seconds, total=10):
    return {"seconds": seconds, "answer": {"total": total, "items": []}}


def test_early_failure_preserves_time_for_fallback_and_total_ceiling():
    early = {"seconds": 2, "error": "ValueError"}
    assert replay(early, stage(25), 60)["seconds"] == 27
    assert replay(early, stage(25), 60)["backend"] == "fallback"
    assert replay(stage(65), stage(25), 60)["backend"] is None
    assert replay(stage(65), stage(25), 60)["seconds"] == 70
    assert replay(stage(65), stage(25), 40)["seconds"] == 65
    assert replay(stage(65), stage(25), 40)["backend"] == "fallback"
    with pytest.raises(ValueError):
        replay(stage(10), stage(5), 70)


def test_success_at_cutoff_and_fallback_at_ceiling_are_inclusive():
    assert replay(stage(60), stage(20), 60)["backend"] == "primary"
    assert replay(stage(61), stage(10), 60)["backend"] == "fallback"
    assert replay(stage(61), stage(10.01), 60)["deadline_miss"]


def test_missing_rows_stay_in_fixed_population_and_cutoff_losses_are_reported():
    truth = {"one": {"total":10,"items":[]}, "missing": {"total":10,"items":[]}}
    result = summary({"one": {"primary":stage(53),"fallback":stage(25,20)}},truth)
    assert result['60']['n'] == result['40']['n'] == 2
    assert result['60']['total_correct'] == 1
    assert result['40']['total_correct'] == 0
    assert result['40']['total_losses'] == 1
    assert result['40']['primary_successes_cut_off'] == 1
    assert result['40']['correct_primary_totals_cut_off'] == 1
    assert result['60']['missing_measurements'] == 1
    assert result['60']['failed'] == 1


def test_numeric_exact_metric_does_not_accept_thousand_scale_ambiguity():
    truth = {"one": {"total": 10000, "items": []}}
    result = summary({"one": {"primary":stage(5,10)}},truth)['60']
    assert result['total_correct'] == 1  # documented legacy CORD comparator
    assert result['total_exact_correct'] == 0


@pytest.mark.parametrize('items', [True, False])
async def test_actual_backend_cutoff_cancels_primary_and_preserves_requested_profile(monkeypatch, items):
    import asyncio
    import time
    from PIL import Image
    import src.main as main
    from src.config import settings
    from src.models import ExtractionOptions, ReceiptResponse, ProcessingMetadata
    from src.vlm_service import VisionLLMService

    options = ExtractionOptions(items=items)
    service = VisionLLMService()
    cancelled = []
    calls = []
    monkeypatch.setattr(settings, 'parser_backend', 'vlm_ollama')
    monkeypatch.setattr(main, 'vlm_service', service)
    monkeypatch.setattr(service, '_payload', lambda image, opts: {})

    async def chat(payload, timeout):
        try:
            await asyncio.sleep(1.25)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return '{"merchant_name":"Example","total":10,"items":[]}'

    async def fallback(image, opts, started, deadline):
        assert opts is options
        calls.append(opts.items)
        await asyncio.sleep(.02)
        return ReceiptResponse(merchant_name='Example', total=20, items=[],
            processing_metadata=ProcessingMetadata(backend='paddleocr_ollama',
            ocr_time_ms=0, llm_time_ms=20, total_time_ms=120, ocr_confidence=1))

    monkeypatch.setattr(service, '_chat', chat)
    monkeypatch.setattr(main, '_parse_with_paddleocr_ollama', fallback)
    image = Image.new('RGB', (10, 10))
    for cutoff, expected in [(1.6, 'vlm_ollama'), (1.05, 'paddleocr_ollama')]:
        monkeypatch.setattr(settings, 'vlm_fallback_reserve_seconds', 2.2-cutoff)
        started = time.monotonic()
        async with asyncio.timeout_at(started+2.2):
            response = await main._run_backends(image, options, time.time(), started+2.2)
        assert response.processing_metadata.backend == expected
        assert time.monotonic()-started < 2.2
    assert calls == [items]
    assert cancelled == [True]


def test_record_confirmed_memory_failure_once_without_retrying_or_dropping_label(tmp_path):
    import json
    from bench.fallback_schedule import record_oom
    (tmp_path/'metadata.json').write_text(json.dumps({'selected':['one']}))
    (tmp_path/'attempt-starts.jsonl').write_text(json.dumps({'id':'one','stage':'fallback','unix_time':10})+'\n')
    state={'OOMKilled':True,'Running':False,'FinishedAt':'1970-01-01T00:00:22Z'}
    row=record_oom(tmp_path,state,'parser-bench-0035-test')
    assert row == {'id':'one','stage':'fallback','error':'OOMKilled','seconds':12}
    assert len((tmp_path/'stages.jsonl').read_text().splitlines()) == 1
    with pytest.raises(ValueError,match='already recorded'):
        record_oom(tmp_path,state,'parser-bench-0035-test')
    assert len((tmp_path/'stages.jsonl').read_text().splitlines()) == 1


def test_record_failure_requires_actual_oom_confirmation(tmp_path):
    from bench.fallback_schedule import record_oom
    with pytest.raises(ValueError,match='confirmed'):
        record_oom(tmp_path,{'OOMKilled':False},'parser-bench-0035-test')


def test_fatal_ingress_or_process_failure_cannot_be_rescued_by_same_request_fallback():
    for error in ['ImageTooLarge', 'CapacityError', 'OOMKilled']:
        result = replay({'seconds':3,'error':error},stage(1),60)
        assert result['backend'] is None
        assert result['seconds'] == 3
        assert result['fatal_stage_failure']
