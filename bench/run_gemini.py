"""WORK-0006: Gemini alone (no fallback) over the same receipts, with retries for 429/503."""
import asyncio, json, sys, time
from pathlib import Path
from PIL import Image
from src.gemini_service import GeminiReceiptService

images, out, limit, pause = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
svc = GeminiReceiptService()
with open(out, "w") as f:
    for p in sorted(images.glob("*.jpg"))[:limit]:
        started, rec = time.monotonic(), None
        for attempt in range(4):
            try:
                t = time.monotonic()
                d = asyncio.run(svc.parse_receipt(Image.open(p), max_retries=1))
                rec = {"raw": d.model_dump_json(), "seconds": round(time.monotonic() - t, 2)}
                break
            except Exception as e:
                rec = {"raw": None, "error": str(e)[:200], "seconds": round(time.monotonic() - started, 2)}
                time.sleep(30)
        rec["id"] = p.stem
        f.write(json.dumps(rec) + "\n"); f.flush()
        print(p.stem, rec["seconds"], rec.get("error", "")[:80], flush=True)
        time.sleep(pause)
