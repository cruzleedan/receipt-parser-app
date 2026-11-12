#!/usr/bin/env bash
# WORK-0009: run the local candidates over the owner's receipts ($DATA/images), all on d3.
# No cloud backend is run: the images include friends' receipts (WORK-0009 handling rules).
set -u
DATA=${DATA:?set DATA to the receipt-bench folder}; OUT=$DATA/runs; mkdir -p "$OUT"
BENCH=$(cd "$(dirname "$0")" && pwd); APP=$(dirname "$BENCH")
docker network inspect bench-0006 >/dev/null 2>&1 || docker network create bench-0006 >/dev/null
docker start ollama-bench-0006 >/dev/null 2>&1 || docker run -d --name ollama-bench-0006 --network bench-0006 \
  --device /dev/dri --group-add "$(getent group render | cut -d: -f3)" --group-add "$(getent group video | cut -d: -f3)" \
  -e OLLAMA_VULKAN=1 -e OLLAMA_IGPU_ENABLE=1 -e OLLAMA_KEEP_ALIVE=30m -v ollama-bench-0006:/root/.ollama ollama/ollama:0.40.12 >/dev/null
until docker exec ollama-bench-0006 ollama list >/dev/null 2>&1; do sleep 2; done
run() { docker run --rm --network bench-0006 -v "$BENCH:/bench:ro" -v "$DATA/${IMAGES:-images}:/images:ro" -v "$OUT:/out" "$@"; }
LIMIT=${LIMIT:-1000}   # IMAGES=sample runs the every-third subset made by the caller
for m in qwen3.5:4b gemma4:e4b glm-ocr:q8_0 hf.co/mradermacher/OvisOCR3-GGUF:Q8_0; do
  tag=$(echo "$m" | tr ':/.' '___')
  echo "== $m"; run bench-runner-0006 sh -c "cd /tmp && python -I /bench/run_bench.py --backend ollama --model $m --images /images --out /out/$tag.jsonl --limit $LIMIT --timeout 180" | tail -1
  docker exec ollama-bench-0006 ollama stop "$m" >/dev/null 2>&1
done
docker rm -f receipt-parser-bench >/dev/null 2>&1
# PaddleOCR model files: reuse a copy (PADDLEX_CACHE, e.g. docker cp receipt-parser-app:/root/.paddlex) — the download can hang.
docker run -d --name receipt-parser-bench --network bench-0006 ${PADDLEX_CACHE:+-v "$PADDLEX_CACHE:/root/.paddlex"} -e DISABLE_MODEL_SOURCE_CHECK=True \
  -e PARSER_BACKEND=paddleocr_ollama -e OLLAMA_HOST=http://ollama-bench-0006:11434 -e OLLAMA_MODEL=llama3.2:3b \
  -e OCR_USE_GPU=false -e FLAGS_use_mkldnn=false -e CPU_NUM=4 receipt-parser-app-parser >/dev/null
until docker exec receipt-parser-bench curl -sf localhost:8000/health >/dev/null 2>&1; do sleep 5; done
echo "== current local pipeline"; run bench-runner-0006 sh -c "cd /tmp && python -I /bench/run_bench.py --backend parser --url http://receipt-parser-bench:8000 --images /images --out /out/current_local.jsonl --limit $LIMIT" | tail -1
docker rm -f receipt-parser-bench >/dev/null 2>&1
docker stop ollama-bench-0006 >/dev/null
echo "== done"
