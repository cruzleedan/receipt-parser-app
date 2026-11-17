"""Compare the prior and corrected fallback on public/fictional fixtures only."""
import argparse
import json
from pathlib import Path
import time
import httpx


def run(args):
    results=[]
    for fixture,expected,minimum_items in [(Path(args.sample),24.10,3),(Path(args.synthetic),80,12)]:
        for name,url in [("before",args.before),("after",args.after)]:
            started=time.monotonic()
            response=httpx.post(url+"/parse",files={"file":(fixture.name,fixture.read_bytes(),"image/png")},timeout=85,trust_env=False)
            body=response.json()
            row={"case":fixture.stem,"version":name,"status":response.status_code,
                 "seconds":round(time.monotonic()-started,2)}
            if response.status_code==200:
                row.update(total=body["total"],items=len(body["items"]),
                           correct_total=abs(body["total"]-expected)<.005,
                           complete_items=len(body["items"])>=minimum_items,
                           backend=body["processing_metadata"].get("backend"),
                           ocr_ms=round(body["processing_metadata"]["ocr_time_ms"]),
                           llm_ms=round(body["processing_metadata"]["llm_time_ms"]))
            ps=httpx.get("http://shared-ollama:11434/api/ps",timeout=5,trust_env=False).json()
            row["gpu_bytes"]=sum(model.get("size_vram",0) for model in ps.get("models",[]))
            results.append(row)
            print(json.dumps(row),flush=True)
            Path(args.out).write_text(json.dumps(results,indent=2))
            if name=="after":
                assert response.status_code==200 and row["correct_total"] and row["complete_items"],row
                assert row["backend"]=="paddleocr_ollama",row
    Path(args.out).write_text(json.dumps(results,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for argument in ("before","after","sample","synthetic","out"):
        parser.add_argument("--"+argument,required=True)
    run(parser.parse_args())
