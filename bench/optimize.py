"""WORK-0032: local-only, paired image/profile experiments; private results stay outside git.

Run from the parser image with src and bench on PYTHONPATH. DATA holds labels.json
and sample/*.jpg. Output contains model answers and must stay in the private corpus.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import platform
import json
import logging
import math
from pathlib import Path
import random
import statistics
import time

from PIL import Image, ImageChops
from src.config import settings
from src.models import ExtractionOptions
from src.vlm_service import VisionLLMService
from src.utils import load_image_from_bytes
from src.http_client import get_json
from consistency import iso_date, merchant
from score_labels import merchant_ok


def metrics(records, labels):
    n = len(labels)
    total = date = store = all_three = missing = 0
    for rid, lab in labels.items():
        record = records.get(rid, {})
        answer = record.get("answer")
        if not answer:
            missing += 1
            continue
        ok_t = abs(answer["total"] - float(str(lab["total"]).replace(",", ""))) <= .005
        ok_d = answer.get("date") is not None and answer.get("date") == iso_date(lab["date"])
        ok_m = merchant_ok(merchant(answer.get("merchant_name")), merchant(lab["merchant"]))
        total += ok_t; date += ok_d; store += ok_m
        all_three += ok_t and ok_d and ok_m
    durations = [record["seconds"] for record in records.values()]
    ordered = sorted(durations)
    percentile = lambda q: ordered[max(0, math.ceil(len(ordered)*q)-1)] if ordered else None
    date_labelled = sum(iso_date(lab.get("date")) is not None for lab in labels.values())
    return {"n":n,"date_labelled":date_labelled,"all_three_labelled":date_labelled,"total_exact":total,"date":date,"merchant":store,"all_three":all_three,
            "missing":missing,"median_s":round(statistics.median(durations),2) if durations else None,
            "p90_s":percentile(.9),"p95_s":percentile(.95),
            "deadline_misses":sum(r.get("error")=="TimeoutError" for r in records.values())}


def crop_white_border(image):
    # Explicit experiment only. Never enabled in production by this harness.
    background = Image.new("RGB", image.size, "white")
    difference = ImageChops.difference(image, background).convert("L")
    box = difference.point(lambda value: 255 if value > 40 else 0).getbbox()
    if not box:
        return image
    left, top, right, bottom = box
    pad = 24
    return image.crop((max(0,left-pad),max(0,top-pad),min(image.width,right+pad),min(image.height,bottom+pad)))


async def run(args):
    # Suppress backend logs: only aggregate progress is emitted, never receipt data.
    logging.disable(logging.CRITICAL)
    data = Path(args.data)
    labels = json.loads((data / "labels.json").read_text())
    eligible = sorted(rid for rid, lab in labels.items()
                      if not lab.get("unreadable") and (data/"sample"/(rid+".jpg")).exists())
    selected = sorted(random.Random(32).sample(eligible, min(args.limit,len(eligible))))
    selected_labels = {rid:labels[rid] for rid in selected}
    out = Path(args.out); out.mkdir(parents=True,exist_ok=True,mode=0o700)
    service = VisionLLMService()
    variants = [("baseline1280",1280,False,False), ("oriented1600",1600,False,False),
                ("oriented1920",1920,False,False), ("core1280",1280,True,False),
                ("crop1280",1280,False,True)]
    tags = await get_json(f"{service.host}/api/tags")
    model_digest = next((m.get("digest") for m in tags.get("models",[]) if m.get("name")==service.model),None)
    source_digest = hashlib.sha256(b"".join(p.read_bytes() for p in sorted(Path("/app/src").glob("*.py")))).hexdigest()
    metadata = {"model_digest":model_digest,"source_digest":source_digest,
                "python":platform.python_version(),
                "packages":{name:importlib.metadata.version(name) for name in ("httpx","Pillow","pydantic")},
                "model":service.model,"num_ctx":settings.vlm_num_ctx,"num_predict":settings.vlm_num_predict,
                "selected":selected,"selection_seed":32,"n":len(selected),
                "note":"Previously used development labels; not an independent held-out accuracy estimate",
                "variants":variants,"input_hashes":{rid:hashlib.sha256((data/"sample"/(rid+".jpg")).read_bytes()).hexdigest() for rid in selected}}
    (out/"metadata.json").write_text(json.dumps(metadata,indent=2))
    results = {name:{} for name,_,_,_ in variants}
    # Interleave arm order to reduce cold-start/load ordering bias.
    for index, rid in enumerate(selected):
        path=data/"sample"/(rid+".jpg")
        for name,side,core,crop in variants[index%len(variants):]+variants[:index%len(variants)]:
            raw=path.read_bytes()
            image=load_image_from_bytes(raw)
            if name=="baseline1280":
                with Image.open(path) as source: image=source.convert("RGB")
            if crop: image=crop_white_border(image)
            settings.vlm_max_side=side
            options=ExtractionOptions(items=not core,time=not core,subtotal=not core,tax=not core)
            started=time.monotonic()
            record={"id":rid}
            try:
                receipt=await service.parse_receipt(image,extraction_options=options,
                            deadline=time.monotonic()+70,reserve_seconds=10)
                record["answer"]=receipt.model_dump()
            except Exception as exc:
                record["error"]=type(exc).__name__
            record["seconds"]=round(time.monotonic()-started,2)
            results[name][rid]=record
            with (out/(name+".jsonl")).open("a") as stream:
                stream.write(json.dumps(record)+"\n")
            print(json.dumps({"progress":f"{index+1}/{len(selected)}","variant":name,
                              "seconds":record["seconds"],"failed":"error" in record}),flush=True)
            await asyncio.sleep(args.pause)
    summary={name:metrics(records,selected_labels) for name,records in results.items()}
    baseline=results["baseline1280"]
    for name, records in results.items():
        wins=losses=0
        for rid in selected:
            base=metrics({rid:baseline[rid]},{rid:selected_labels[rid]})["all_three"]
            other=metrics({rid:records[rid]},{rid:selected_labels[rid]})["all_three"]
            wins+=other>base; losses+=other<base
        summary[name].update(paired_all_three_wins=wins,paired_all_three_losses=losses)
    (out/"summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps({"summary":summary}),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--limit",type=int,default=8)
    parser.add_argument("--pause",type=float,default=1)
    asyncio.run(run(parser.parse_args()))
