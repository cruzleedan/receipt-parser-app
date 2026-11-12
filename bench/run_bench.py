"""WORK-0006: run one backend over a folder of receipt images and write one JSON line per receipt.

Usage (inside a container on the benchmark network):
  python -I bench/run_bench.py --backend ollama --model qwen3.5:4b --images /data/cord --out /out/qwen35.jsonl
  python -I bench/run_bench.py --backend parser --url http://receipt-parser-bench:8000 ...
Backends:
  ollama  - one vision model reads the image; JSON schema enforced through Ollama `format`.
  parser  - the receipt-parser-app /parse endpoint (current pipeline, or Gemini).
  donut   - naver-clova-ix/donut-base-finetuned-cord-v2 on CPU (CORD baseline).
"""

import argparse
import base64
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

SCHEMA = {
    "type": "object",
    "properties": {
        "merchant_name": {"type": ["string", "null"]},
        "date": {"type": ["string", "null"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "total_price": {"type": ["number", "null"]},
                },
                # Every key required (null allowed): otherwise models drop optional fields.
                "required": ["name", "quantity", "unit_price", "total_price"],
            },
        },
        "subtotal": {"type": ["number", "null"]},
        "tax": {"type": ["number", "null"]},
        "total": {"type": ["number", "null"]},
    },
    "required": ["merchant_name", "date", "items", "subtotal", "tax", "total"],
}

TEMPLATE = {
    "merchant_name": "",
    "date": "",
    "items": [{"name": "", "quantity": 0, "unit_price": 0, "total_price": 0}],
    "subtotal": 0,
    "tax": 0,
    "total": 0,
}

GENERIC_PROMPT = (
    "Read this receipt and return its data as JSON with these fields: merchant_name, date (YYYY-MM-DD), "
    "items (each: name, quantity, unit_price, total_price), subtotal, tax, total. "
    "Copy amounts as plain numbers exactly as printed, without currency symbols. "
    "Use null for anything not printed. Return only the JSON."
)
# WORK-0008 prompt variants for the generic (Qwen/Gemma) path.
VARIANT_PROMPTS = {
    "v1": (
        "Read this receipt and return its data as JSON with these fields: merchant_name, date, "
        "items (each: name, quantity, unit_price, total_price), subtotal, tax, total.\n"
        "- merchant_name: the store or business name at the top, not the address or the operator company.\n"
        "- date: the transaction date copied exactly as printed on the receipt, including the year; "
        "do not reorder or convert it.\n"
        "- total: the final amount due for the purchase (the line labelled TOTAL, AMOUNT DUE or similar), "
        "not the cash tendered, the change, or the VATable/subtotal amount.\n"
        "Copy amounts as plain numbers without currency symbols. Use null for anything not printed. "
        "Return only the JSON."
    ),
}
PROMPTS = {
    # GLM-OCR's documented extraction prompt (model card): Chinese instruction + JSON template.
    "glm-ocr": "请按下列JSON格式输出图中信息:\n" + json.dumps(TEMPLATE, ensure_ascii=False),
    # OvisOCR3 schema-template mode (model card describes prompting with a template).
    "ovisocr3": "Extract the information in the image following this JSON template:\n"
    + json.dumps(TEMPLATE),
}


def image_b64(path: Path, max_side: int) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def post_json(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# WORK-0010: NuExtract3 is prompted with its own roles (model template): a typed template, optional
# instructions, and the image in the user message. Types per its card: verbatim-string, date, number.
NUEXTRACT_TEMPLATE = {
    "merchant_name": "verbatim-string",
    "date": "date",
    "items": [{"name": "verbatim-string", "quantity": "number", "unit_price": "number", "total_price": "number"}],
    "subtotal": "number",
    "tax": "number",
    "total": "number",
}
NUEXTRACT_INSTRUCTIONS = (
    "merchant_name is the store or business name at the top. total is the final amount due for the "
    "purchase, not the cash tendered, the change or the VATable amount. Philippine receipts print "
    "dates month first (MM/DD/YY)."
)


def run_nuextract(args, path: Path) -> dict:
    messages = [{"role": "template", "content": json.dumps(NUEXTRACT_TEMPLATE)}]
    if args.variant == "v1":
        messages.append({"role": "instructions", "content": NUEXTRACT_INSTRUCTIONS})
    messages.append({"role": "user", "content": "", "images": [image_b64(path, args.max_side)]})
    payload = {
        "model": args.model, "messages": messages, "stream": False, "think": False, "keep_alive": "30m",
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2048},
    }
    res = post_json(f"{args.url}/api/chat", payload, args.timeout)
    return {"raw": res["message"]["content"], "prompt_eval_ms": res.get("prompt_eval_duration", 0) / 1e6,
            "eval_ms": res.get("eval_duration", 0) / 1e6}


def run_ollama(args, path: Path) -> dict:
    if "nuextract" in args.model.lower():
        return run_nuextract(args, path)
    prompt = VARIANT_PROMPTS.get(args.variant, GENERIC_PROMPT)
    for key, p in PROMPTS.items():
        if key in args.model.lower():
            prompt = p
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt, "images": [image_b64(path, args.max_side)]}],
        "stream": False,
        "format": SCHEMA,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2048},
    }
    if args.no_think_field:
        payload.pop("think")
    res = post_json(f"{args.url}/api/chat", payload, args.timeout)
    return {
        "raw": res["message"]["content"],
        "prompt_eval_ms": res.get("prompt_eval_duration", 0) / 1e6,
        "eval_ms": res.get("eval_duration", 0) / 1e6,
    }


def run_parser(args, path: Path) -> dict:
    boundary = "----bench0006"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{args.url}/parse", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"raw": None, "error": f"HTTP {e.code}"}
    backend = "gemini" if data.get("processing_metadata", {}).get("ocr_time_ms") == 0 else "local"
    return {"raw": json.dumps(data), "backend": backend}


_donut = {}


def run_donut(args, path: Path) -> dict:
    import re
    import torch
    from transformers import DonutProcessor, VisionEncoderDecoderModel

    if not _donut:
        name = "naver-clova-ix/donut-base-finetuned-cord-v2"
        _donut["p"] = DonutProcessor.from_pretrained(name)
        _donut["m"] = VisionEncoderDecoderModel.from_pretrained(name).eval()
    p, m = _donut["p"], _donut["m"]
    pixel_values = p(Image.open(path).convert("RGB"), return_tensors="pt").pixel_values
    prompt_ids = p.tokenizer("<s_cord-v2>", add_special_tokens=False, return_tensors="pt").input_ids
    with torch.no_grad():
        out = m.generate(
            pixel_values, decoder_input_ids=prompt_ids, max_length=m.decoder.config.max_position_embeddings,
            pad_token_id=p.tokenizer.pad_token_id, eos_token_id=p.tokenizer.eos_token_id,
            use_cache=True, bad_words_ids=[[p.tokenizer.unk_token_id]], num_beams=1,
        )
    seq = p.batch_decode(out)[0].replace(p.tokenizer.eos_token, "").replace(p.tokenizer.pad_token, "")
    seq = re.sub(r"<.*?>", "", seq, count=1).strip()
    return {"raw": json.dumps(p.token2json(seq)), "format": "cord"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["ollama", "parser", "donut"], required=True)
    ap.add_argument("--model", default="")
    ap.add_argument("--url", default="http://ollama-bench-0006:11434")
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--max-side", type=int, default=1280)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--pause", type=float, default=0)
    ap.add_argument("--no-think-field", action="store_true")
    ap.add_argument("--variant", default="v0", help="v0 = WORK-0006/0009 prompt; v1 = WORK-0008 date-as-printed prompt")
    args = ap.parse_args()

    runner = {"ollama": run_ollama, "parser": run_parser, "donut": run_donut}[args.backend]
    images = sorted(Path(args.images).glob("*.jpg"))[: args.limit]
    with open(args.out, "w") as out:
        for i, path in enumerate(images):
            started = time.monotonic()
            try:
                rec = runner(args, path)
            except Exception as e:  # recorded, not fatal: a failure is a result
                rec = {"raw": None, "error": f"{type(e).__name__}: {e}"[:300]}
            rec.update(id=path.stem, seconds=round(time.monotonic() - started, 2))
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"{i + 1}/{len(images)} {path.stem} {rec['seconds']}s {'ERR ' + rec['error'] if rec.get('error') else ''}", flush=True)
            if args.pause:
                time.sleep(args.pause)
    return 0


if __name__ == "__main__":
    sys.exit(main())
