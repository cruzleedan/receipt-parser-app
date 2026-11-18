#!/usr/bin/env bash
# Local-only WORK-0035 capture. DATA is the cached 100-image CORD directory.
# OUT is a dedicated private result directory, outside Git. Never mount customer data for this run.
set -euo pipefail
: "${DATA:?Set DATA to the absolute cached CORD directory}"
: "${OUT:?Set OUT to a dedicated absolute output directory outside Git}"
[[ "$DATA" = /* && "$OUT" = /* ]] || { echo 'DATA and OUT must be absolute' >&2; exit 2; }
APP="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${IMAGE:-receipt-parser-app-parser:review-final-20261117}"
mkdir -p "$OUT/capture"
chmod 700 "$OUT" "$OUT/capture"
args=()
[[ ! -f "$OUT/capture/metadata.json" ]] || args=(--resume)
for attempt in $(seq 1 32); do
  task_container="parser-bench-0035-$(date +%s)-${attempt}"
  if docker run --name "$task_container" --network container:receipt-parser-app --cpus 4 --memory 4g \
    -e PARSER_BACKEND=vlm_ollama -e VLM_HOST=http://parser-ollama:11434 -e VLM_KEEP_ALIVE=-1 \
    -e OLLAMA_HOST=http://shared-ollama:11434 -e OLLAMA_MODEL=llama3.2-gpu:latest -e OLLAMA_NUM_GPU=0 \
    -e FLAGS_use_mkldnn=false -e FLAGS_use_onednn=false -e FLAGS_enable_pir_api=false -e CPU_NUM=4 \
    -v "$APP/bench:/app/bench:ro" -v "$APP/src:/app/src:ro" -v "$DATA:/data:ro" \
    -v "$OUT:/results" -v receipt-parser-app_parser-ocr-models:/root/.paddlex:ro \
    --entrypoint python "$IMAGE" -m bench.fallback_schedule \
    --data /data --out /results/capture --limit 30 "${args[@]}"; then
      docker rm "$task_container" >/dev/null
      exit 0
  fi
  # Refuses non-OOM exits and duplicate stages. Failed stages stay failed; only later work resumes.
  (cd "$APP" && python3 -m bench.fallback_schedule --data "$DATA" --out "$OUT/capture" --record-oom "$task_container")
  docker rm "$task_container" >/dev/null
  args=(--resume)
done
echo 'Stopped after bounded restart count; inspect remaining missing stages' >&2
exit 1
