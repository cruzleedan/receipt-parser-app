"""Public-fixture load check: 1/2/4 concurrent calls and health latency under load."""
import argparse
import asyncio
import json
from pathlib import Path
import time
import httpx


async def run(args):
    image=Path(args.image).read_bytes()
    results=[]
    async with httpx.AsyncClient(base_url=args.url,timeout=85,trust_env=False) as client:
        for concurrency in (1,2,4):
            times=[]; health=[]
            async def parse():
                started=time.monotonic()
                response=await client.post("/parse",files={"file":("public.png",image,"image/png")})
                times.append((response.status_code,round(time.monotonic()-started,3)))
                if response.status_code==200:
                    body=response.json()
                    assert abs(body["total"]-24.10)<.01, "Public sample total changed"
                    assert body["processing_metadata"]["backend"]=="vlm_ollama"
                return response.status_code
            tasks=[asyncio.create_task(parse()) for _ in range(concurrency)]
            while not all(task.done() for task in tasks):
                started=time.monotonic()
                response=await client.get("/ready")
                assert response.status_code==200
                health.append(time.monotonic()-started)
                await asyncio.sleep(.2)
            codes=await asyncio.gather(*tasks)
            assert codes.count(200)==1 and codes.count(503)==concurrency-1, codes
            record={"concurrency":concurrency,"responses":times,
                    "health_max_s":round(max(health),3),"health_samples":len(health)}
            results.append(record)
            print(json.dumps(record),flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps(results,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",required=True)
    parser.add_argument("--image",required=True)
    parser.add_argument("--out")
    asyncio.run(run(parser.parse_args()))
