#!/usr/bin/env bash
# WORK-0006: run every candidate over the first $LIMIT CORD-v2 test receipts, one at a time.
# Needs: network bench-0006 with ollama-bench-0006 (Vulkan iGPU), images + truth in $OUT/cord,
# images bench-runner-0006 (Pillow) and bench-donut-0006 (Torch CPU), receipt-parser-app-parser.
set -u
OUT=${OUT:?set OUT to the results folder}; LIMIT=${LIMIT:-50}
BENCH=$(cd "$(dirname "$0")" && pwd); APP=$(dirname "$BENCH")
run() { docker run --rm --network bench-0006 -v "$BENCH:/bench:ro" -v "$OUT:/out" "$@"; }
for m in qwen3.5:4b gemma4:e4b glm-ocr:q8_0 hf.co/mradermacher/OvisOCR3-GGUF:Q8_0; do
  until docker exec ollama-bench-0006 ollama show "$m" >/dev/null 2>&1; do sleep 30; done
  tag=$(echo "$m" | tr ':/.' '___')
  echo "== $m"; run bench-runner-0006 sh -c "cd /tmp && python -I /bench/run_bench.py --backend ollama --model $m --images /out/cord --out /out/$tag.jsonl --limit $LIMIT" | tail -1
  docker exec ollama-bench-0006 ollama stop "$m" >/dev/null 2>&1
done
# Current production pipelines through the real parser image (OCR on CPU, llama3.2 3B with num_gpu 0 as in production).
docker exec ollama-bench-0006 ollama pull llama3.2:3b >/dev/null
for backend in paddleocr_ollama gemini; do
  docker rm -f receipt-parser-bench >/dev/null 2>&1
  docker run -d --name receipt-parser-bench --network bench-0006 --env-file "$APP/.env" \
    -e PARSER_BACKEND=$backend -e OLLAMA_HOST=http://ollama-bench-0006:11434 -e OLLAMA_MODEL=llama3.2:3b \
    -e OCR_USE_GPU=false -e FLAGS_use_mkldnn=false -e CPU_NUM=4 receipt-parser-app-parser >/dev/null
  until docker exec receipt-parser-bench curl -sf localhost:8000/health >/dev/null 2>&1; do sleep 5; done
  pause=0; [ $backend = gemini ] && pause=7   # free-tier rate limit
  echo "== parser $backend"; run bench-runner-0006 sh -c "cd /tmp && python -I /bench/run_bench.py --backend parser --url http://receipt-parser-bench:8000 --images /out/cord --out /out/parser_$backend.jsonl --limit $LIMIT --pause $pause" | tail -1
done
docker rm -f receipt-parser-bench >/dev/null 2>&1
echo "== donut"; run -v bench-donut-cache:/root/.cache bench-donut-0006 sh -c "cd /tmp && python -I /bench/run_bench.py --backend donut --images /out/cord --out /out/donut_cord_v2.jsonl --limit $LIMIT" | tail -1
echo "== done"
