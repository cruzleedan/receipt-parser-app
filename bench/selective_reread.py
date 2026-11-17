"""WORK-0032 prototype: confidence-triggered header/footer re-read, local data only.

This evaluates an experimental policy; it never changes production extraction.
Use the output directory from optimize.py after that run has completed.
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import time

from PIL import Image
from src.config import settings
from src.models import ExtractionOptions
from src.utils import load_image_from_bytes
from src.vlm_service import VisionLLMService
from optimize import metrics
from consistency import iso_date


class RegionService(VisionLLMService):
    def _payload(self,image,options):
        payload=super()._payload(image,options)
        payload["messages"][0]["content"] += (
            " The image contains the header and footer of one receipt; its middle is omitted. "
            "Do not infer missing fields."
        )
        return payload


async def run(args):
    logging.disable(logging.CRITICAL)
    data,out=Path(args.data),Path(args.out)
    metadata=json.loads((out/"metadata.json").read_text())
    labels_all=json.loads((data/"labels.json").read_text())
    labels={rid:labels_all[rid] for rid in metadata["selected"]}
    baseline={row["id"]:row for row in map(json.loads,(out/"baseline1280.jsonl").read_text().splitlines())}
    service=RegionService()
    settings.vlm_max_side=1920
    results={}; flagged=calls=budget_skips=disagreements=0
    for rid in metadata["selected"]:
        base=baseline[rid]
        answer=base.get("answer") or {}
        confidence=answer.get("field_confidence") or {}
        fields=[field for field in ("date","total") if answer.get(field) is None
                or confidence.get(field) is None or confidence[field]<args.threshold]
        remaining=max(0,60-base["seconds"])
        record={"id":rid,"answer":answer or None,"seconds":base["seconds"],"flagged_fields":fields}
        if fields:
            flagged+=1
            if remaining<1:
                budget_skips+=1
            else:
                started=time.monotonic()
                image=load_image_from_bytes((data/"sample"/(rid+".jpg")).read_bytes())
                edge=max(1,round(image.height*.35))
                if image.height>image.width*2:
                    region=Image.new("RGB",(image.width,edge*2),"white")
                    region.paste(image.crop((0,0,image.width,edge)),(0,0))
                    region.paste(image.crop((0,image.height-edge,image.width,image.height)),(0,edge))
                else:
                    region=image
                calls+=1
                try:
                    alternate=await service.parse_receipt(region,
                        extraction_options=ExtractionOptions(items=False,time=False,subtotal=False,tax=False),
                        deadline=started+remaining,reserve_seconds=0)
                    alternate=alternate.model_dump()
                    record["reread"]=alternate
                    merged=dict(answer) if answer else dict(alternate)
                    alternate_conf=alternate.get("field_confidence") or {}
                    for field in fields:
                        if alternate.get(field) is not None and alternate.get(field)!=answer.get(field):
                            disagreements+=1
                        if alternate.get(field) is not None and (answer.get(field) is None or
                            (alternate_conf.get(field) or 0)>(confidence.get(field) or 0)):
                            merged[field]=alternate[field]
                    record["answer"]=merged
                except Exception as exc:
                    record["reread_error"]=type(exc).__name__
                record["seconds"]=round(base["seconds"]+time.monotonic()-started,2)
        results[rid]=record
        with (out/"selective1920.jsonl").open("a") as stream:
            stream.write(json.dumps(record)+"\n")
    summary=metrics(results,labels)
    baseline_metrics=metrics(baseline,labels)
    confident_wrong=0; wrong=0; wrong_dates=0; confident_wrong_dates=0
    for rid,row in baseline.items():
        answer=row.get("answer") or {}; conf=answer.get("field_confidence") or {}
        truth=float(str(labels[rid]["total"]).replace(",",""))
        if answer.get("total") is not None and abs(answer["total"]-truth)>.005:
            wrong+=1; confident_wrong+=(conf.get("total") or 0)>=args.threshold
        if iso_date(labels[rid]["date"]) is not None and answer.get("date") != iso_date(labels[rid]["date"]):
            wrong_dates+=1; confident_wrong_dates+=(conf.get("date") or 0)>=args.threshold
    summary.update(baseline_wrong_dates=wrong_dates,
                   baseline_confident_wrong_dates=confident_wrong_dates,
                   reread_failures=sum("reread_error" in row for row in results.values()),
                   reread_timeouts=sum(row.get("reread_error")=="TimeoutError" for row in results.values()),
                   flagged_receipts=flagged,reread_calls=calls,budget_skips=budget_skips,
                   field_disagreements=disagreements,threshold=args.threshold,
                   baseline_wrong_totals=wrong,baseline_confident_wrong_totals=confident_wrong,
                   baseline=baseline_metrics,
                   note="Development-only uncalibrated policy; no production adoption")
    (out/"selective-summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--threshold",type=float,default=.9)
    asyncio.run(run(parser.parse_args()))
