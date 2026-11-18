"""WORK-0035: local timing capture and explicitly counterfactual schedule replay.

Raw images, labels and answers remain outside Git. No runtime scheduling policy
is changed. Replay assumes backend durations do not change after primary abort;
actual schedule validation is needed before promoting any result.
"""
import argparse
import datetime
import os
import subprocess
import tempfile
import asyncio
import hashlib
import json
import logging
import math
from pathlib import Path
import random
import statistics
import time

from bench.score import truth_fields, same_amount, item_counts


def replay(primary, fallback, cutoff, ceiling=70):
    """Replay serial stages, preserving early failures and the total deadline."""
    if not 0 < cutoff < ceiling:
        raise ValueError("cutoff must be inside total deadline")
    if primary is None:
        return {"backend": None, "seconds": ceiling, "missing_measurement": True}
    if primary.get('error') in ('ImageTooLarge','UnidentifiedImageError','DecompressionBombError','CapacityError','OOMKilled'):
        return {'backend':None,'seconds':min(primary['seconds'],ceiling),'fatal_stage_failure':True}
    elapsed = min(primary["seconds"], cutoff)
    if primary.get("answer") is not None and primary["seconds"] <= cutoff:
        return {"backend": "primary", "seconds": elapsed, "answer": primary["answer"]}
    if fallback is None:
        return {"backend": None, "seconds": ceiling, "missing_measurement": True}
    duration = elapsed + fallback["seconds"]
    if fallback.get("answer") is not None and duration <= ceiling:
        return {"backend": "fallback", "seconds": duration, "answer": fallback["answer"]}
    return {"backend": None, "seconds": min(ceiling, duration),
            "deadline_miss": duration >= ceiling}


def quality(answer, truth):
    if answer is None:
        return {"total": False, "total_exact": False, "items": (0, 0, len(truth["items"]))}
    predicted = [(i["name"], i.get("total_price")) for i in answer.get("items", [])]
    return {"total": same_amount(answer.get("total"), truth["total"]),
            "total_exact": truth["total"] is not None and isinstance(answer.get("total"), (int,float)) and abs(answer["total"]-truth["total"]) <= .005,
            "items": item_counts(predicted, truth["items"])}


def summary(records, truths, cutoffs=(60, 50, 45, 40)):
    # Ground truth defines the population; missing/failed captures never disappear.
    n = len(truths)
    output = {}
    baseline = {rid: replay(records.get(rid, {}).get("primary"),
                            records.get(rid, {}).get("fallback"), 60) for rid in truths}
    for cutoff in cutoffs:
        counts = dict(n=n, total_eligible=sum(t["total"] is not None for t in truths.values()),
                      total_correct=0, total_exact_correct=0, primary=0, fallback=0, failed=0,
                      missing_measurements=0, deadline_misses=0,
                      total_wins=0, total_losses=0, exact_total_wins=0, exact_total_losses=0, primary_successes_cut_off=0,
                      correct_primary_totals_cut_off=0)
        tp = predicted = labelled = 0
        durations = []
        for rid, truth in truths.items():
            stages = records.get(rid, {})
            result = replay(stages.get("primary"), stages.get("fallback"), cutoff)
            base_q = quality(baseline[rid].get("answer"), truth)
            q = quality(result.get("answer"), truth)
            counts["total_correct"] += q["total"]
            counts["total_exact_correct"] += q["total_exact"]
            counts[result["backend"] or "failed"] += 1
            counts["missing_measurements"] += result.get("missing_measurement", False)
            counts["deadline_misses"] += result.get("deadline_miss", False)
            counts["total_wins"] += q["total"] > base_q["total"]
            counts["total_losses"] += q["total"] < base_q["total"]
            counts["exact_total_wins"] += q["total_exact"] > base_q["total_exact"]
            counts["exact_total_losses"] += q["total_exact"] < base_q["total_exact"]
            primary = stages.get("primary")
            if primary and primary.get("answer") is not None and cutoff < primary["seconds"] <= 60:
                counts["primary_successes_cut_off"] += 1
                counts["correct_primary_totals_cut_off"] += quality(primary["answer"], truth)["total"]
            a, b, c = q["items"]
            tp += a; predicted += b; labelled += c
            durations.append(result["seconds"])
        ordered = sorted(durations)
        counts.update(item_tp=tp, item_predictions=predicted, item_truth=labelled,
                      item_f1=2*tp/(predicted+labelled) if predicted+labelled else None,
                      median_s=statistics.median(durations) if durations else None,
                      p90_s=ordered[max(0, math.ceil(n*.9)-1)] if n else None,
                      p95_s=ordered[max(0, math.ceil(n*.95)-1)] if n else None)
        output[str(cutoff)] = counts
    return output


def record_oom(out, state, container):
    """Record an externally confirmed failed stage without losing the fixed denominator."""
    if not state.get('OOMKilled') or state.get('Running'):
        raise ValueError('only a confirmed, stopped OOM may be recorded')
    start=json.loads((out/'attempt-starts.jsonl').read_text().splitlines()[-1])
    selected=json.loads((out/'metadata.json').read_text())['selected']
    if start['id'] not in selected or start['stage'] not in ('primary','fallback'):
        raise ValueError('failure is outside frozen population')
    finished=datetime.datetime.fromisoformat(state['FinishedAt'].replace('Z','+00:00')).timestamp()
    elapsed=finished-start['unix_time']
    if elapsed < 0 or not math.isfinite(elapsed):
        raise ValueError('invalid failure timing')
    row={'id':start['id'],'stage':start['stage'],'error':'OOMKilled','seconds':elapsed}
    path=out/'stages.jsonl'
    rows=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if any(r['id']==row['id'] and r['stage']==row['stage'] for r in rows):
        raise ValueError('stage already recorded; do not score a retry')
    for path,entry in [(path,row),(out/'oom-events.jsonl',{'container':container,**row,'state':state})]:
        old=path.read_text() if path.exists() else ''
        with tempfile.NamedTemporaryFile('w',dir=out,delete=False) as stream:
            stream.write(old+json.dumps(entry)+'\n');temporary=stream.name
        os.replace(temporary,path)
    return row


def atomic_json(path, value):
    # Results may have been created by the container user; replace within the private output directory.
    with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False) as stream:
        json.dump(value,stream,indent=2);temporary=stream.name
    os.replace(temporary,path)


def summarize_capture(data, out):
    selected = json.loads((out/'metadata.json').read_text())['selected']
    if len(selected) != len(set(selected)):
        raise ValueError('duplicate frozen population IDs')
    truths = {rid:truth_fields(json.loads((data/(rid+'.json')).read_text())) for rid in selected}
    records = {}
    for line in (out/'stages.jsonl').read_text().splitlines():
        row = json.loads(line)
        rid, stage = row['id'], row['stage']
        if rid not in truths or stage not in ('primary','fallback'):
            raise ValueError('unexpected capture row')
        stages = records.setdefault(rid,{})
        if stage in stages:
            raise ValueError('duplicate captured stage')
        stages[stage] = row
    result = summary(records,truths)
    atomic_json(out/'summary.json', result)
    stage_stats = {}
    for name in ('primary','fallback'):
        captured = [r[name] for r in records.values() if name in r]
        durations = sorted(r['seconds'] for r in captured)
        correct = exact = tp = predictions = truth_count = 0
        for rid,truth in truths.items():
            q = quality(records.get(rid,{}).get(name,{}).get('answer'),truth)
            correct += q['total']; exact += q['total_exact']
            a,b,c=q['items']; tp+=a; predictions+=b; truth_count+=c
        stage_stats[name] = {
            'n':len(truths),'captured':len(captured),
            'successful':sum('answer' in r for r in captured),
            'total_correct':correct,'total_exact_correct':exact,
            'item_f1':2*tp/(predictions+truth_count) if predictions+truth_count else None,
            'median_s':statistics.median(durations) if durations else None,
            'p90_s':durations[max(0,math.ceil(len(durations)*.9)-1)] if durations else None,
            'p95_s':durations[max(0,math.ceil(len(durations)*.95)-1)] if durations else None,
            'timeouts':sum(r.get('error')=='TimeoutError' for r in captured),
            'memory_kills':sum(r.get('error')=='OOMKilled' for r in captured)}
    atomic_json(out/'stage-summary.json', stage_stats)
    # Conditional stress replay only: this is not an observed primary failure rate.
    stalled = {rid:{**stages,'primary':({'seconds':60,'error':'AssumedStall'}
                if stages.get('primary',{}).get('error') != 'ImageTooLarge' else stages['primary'])}
               for rid,stages in records.items()}
    stress = summary(stalled,truths)
    atomic_json(out/'assumed-stall-summary.json', stress)
    return {'schedules':result,'stage_timings':stage_stats,'assumed_primary_stall':stress}


async def validate_schedules(args):
    """Actual serial scheduling on the three slowest captured primary cases."""
    logging.disable(logging.CRITICAL)
    from src.config import settings
    from src.models import ExtractionOptions
    from src.vlm_service import VisionLLMService
    from src.llm_service import OllamaLLMService
    from src.ocr_service import ReceiptOCRService
    from src.utils import load_image_from_bytes
    from src.workers import image_worker
    import src.main as main
    data,out=Path(args.data),Path(args.out)
    rows=[json.loads(line) for line in (out/'stages.jsonl').read_text().splitlines()]
    primary={r['id']:r for r in rows if r['stage']=='primary'}
    population=json.loads((out/'metadata.json').read_text())['selected']
    if set(primary)!=set(population):
        raise ValueError('finish the fixed population before choosing validation cases')
    selected=sorted(primary,key=lambda rid:(-primary[rid]['seconds'],rid))[:3]
    failures=sorted(rid for rid,row in primary.items() if row.get('error') not in
                    (None,'ImageTooLarge','OOMKilled','CapacityError'))
    if failures and failures[0] not in selected:
        selected.append(failures[0])
    metadata={'selected':selected,'rule':'three slowest primary cases plus at most one observed nonfatal primary failure; stress validation, not independent accuracy sample',
              'cutoffs':[60,50,40],'ceiling_s':70,'items':True}
    (out/'validation-metadata.json').write_text(json.dumps(metadata,indent=2))
    settings.parser_backend='vlm_ollama'
    settings.ollama_num_gpu=0
    main.vlm_service=VisionLLMService()
    main.ocr_service=ReceiptOCRService(use_gpu=False)
    main.llm_service=OllamaLLMService()
    options=ExtractionOptions()
    with (out/'validation.jsonl').open('x') as stream:
        for index,rid in enumerate(selected):
            cutoffs=[60,50,40]
            for cutoff in cutoffs[index:]+cutoffs[:index]:
                settings.vlm_fallback_reserve_seconds=70-cutoff
                started=time.monotonic()
                row={'id':rid,'cutoff':cutoff}
                try:
                    async with asyncio.timeout_at(started+70):
                        image=await image_worker.run(load_image_from_bytes,(data/(rid+'.jpg')).read_bytes())
                        answer=await main._run_backends(image,options,time.time(),started+70)
                        if hasattr(answer,'status_code'):
                            row['error']=f'HTTP {answer.status_code}'
                        else:
                            row['answer']=answer.model_dump()
                            row['backend']=answer.processing_metadata.backend
                except Exception as exc:
                    row['error']=type(exc).__name__
                row['seconds']=time.monotonic()-started
                stream.write(json.dumps(row)+'\n');stream.flush()
                print(json.dumps({'validation_case':index+1,'cutoff':cutoff,
                    'seconds':round(row['seconds'],2),'success':'answer' in row,
                    'backend':row.get('backend')}),flush=True)


async def measure(args):
    # No backend logger may print image/label/answer content.
    logging.disable(logging.CRITICAL)
    from src.config import settings
    from src.models import ExtractionOptions
    from src.vlm_service import VisionLLMService
    from src.llm_service import OllamaLLMService
    from src.ocr_service import ReceiptOCRService
    from src.utils import load_image_from_bytes
    from src.workers import image_worker
    from src.http_client import get_json
    import src.main as main

    data, out = Path(args.data), Path(args.out)
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not args.resume and any(out.iterdir()):
        raise FileExistsError('use an empty output directory or --resume')
    eligible = [f"{i:03d}" for i in range(50, 100)]
    selected = sorted(random.Random(35).sample(eligible, args.limit))
    assert all((data/(rid+ext)).exists() for rid in selected for ext in (".jpg", ".json"))
    images = {rid: hashlib.sha256((data/(rid+".jpg")).read_bytes()).hexdigest() for rid in selected}
    truths = {rid: truth_fields(json.loads((data/(rid+".json")).read_text())) for rid in selected}
    primary = VisionLLMService()
    main.ocr_service = ReceiptOCRService(use_gpu=False)
    main.llm_service = OllamaLLMService()
    options = ExtractionOptions()
    settings.ollama_num_gpu = 0
    models = {}
    for name, host in [("primary", settings.vlm_host), ("fallback", settings.ollama_host)]:
        models[name] = await get_json(host+"/api/tags")
    metadata = {"seed":35, "selected":selected, "input_hashes":images,
        "truth_hashes":{rid:hashlib.sha256((data/(rid+".json")).read_bytes()).hexdigest() for rid in selected},
        "profiles":{"full":options.model_dump()}, "source_hashes":{
            str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('/app/src').glob('*.py'))},
        "settings":{key:getattr(settings,key) for key in ["vlm_model","vlm_max_side","vlm_num_ctx","vlm_num_predict","vlm_timeout","ollama_model","ollama_num_ctx","ollama_num_predict","ollama_num_gpu"]},
        "models":models,"kind":"independent cached CORD IDs 050-099; model pretraining overlap unknown",
        "replay_limit":"isolated stage timings; no measured cancellation/queue overlap", "ceiling_s":70}
    if not args.resume:
        (out/'metadata.json').write_text(json.dumps(metadata,indent=2))
    results = {}
    if args.resume:
        saved = json.loads((out/'metadata.json').read_text())
        if saved['input_hashes'] != images or saved['selected'] != selected:
            raise ValueError('resume input population changed')
        for line in (out/'stages.jsonl').read_text().splitlines():
            row = json.loads(line)
            stages = results.setdefault(row['id'], {})
            if row['stage'] in stages:
                raise ValueError('duplicate resumed stage')
            stages[row['stage']] = row
    for index, rid in enumerate(selected):
        stages = results.get(rid,{})
        for name in (["primary","fallback"] if index%2==0 else ["fallback","primary"]):
            if name in stages:
                continue
            with (out/'attempt-starts.jsonl').open('a') as stream:
                stream.write(json.dumps({'id':rid,'stage':name,'unix_time':time.time()})+'\n')
            started = time.monotonic()
            record = {}
            try:
                async with asyncio.timeout(70):
                    image = await image_worker.run(load_image_from_bytes, (data/(rid+'.jpg')).read_bytes())
                    if name == "primary":
                        receipt = await primary.parse_receipt(image, options, deadline=started+70, reserve_seconds=10)
                    else:
                        receipt = await main._parse_with_paddleocr_ollama(image, options, time.time(), started+70)
                    if hasattr(receipt, 'status_code'):
                        record['error'] = f"HTTP {receipt.status_code}"
                    else:
                        record['answer'] = receipt.model_dump()
            except Exception as exc:
                record['error'] = type(exc).__name__
            record['seconds'] = time.monotonic()-started
            stages[name] = record
            with (out/'stages.jsonl').open('a') as stream:
                stream.write(json.dumps({"id":rid,"stage":name,**record})+'\n')
            print(json.dumps({"progress":index+1,"n":len(selected),"stage":name,
                              "seconds":round(record['seconds'],2),"success":"answer" in record}),flush=True)
        results[rid] = stages
        (out/'summary.json').write_text(json.dumps(summary(results,truths),indent=2))
    print(json.dumps({"summary":summary(results,truths)}),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--limit', type=int, default=30, choices=range(1,51))
    parser.add_argument('--summarize', action='store_true')
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--record-oom', metavar='CONTAINER')
    args = parser.parse_args()
    if args.record_oom:
        if not args.record_oom.startswith('parser-bench-0035-'):
            raise ValueError('inspect only this experiment\'s containers')
        state = json.loads(subprocess.check_output(['docker','inspect',args.record_oom]))[0]['State']
        row = record_oom(Path(args.out),state,args.record_oom)
        print(json.dumps({'recorded_failed_stage':row['stage'],'seconds':row['seconds']}))
    elif args.validate:
        asyncio.run(validate_schedules(args))
    elif args.summarize:
        print(json.dumps(summarize_capture(Path(args.data),Path(args.out)),indent=2))
    else:
        asyncio.run(measure(args))
