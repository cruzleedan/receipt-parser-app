# Receipt-parsing benchmark (WORK-0006)

Scores receipt backends against CORD-v2 test ground truth. Results and method: `context/work/0006-local-vision-model-benchmark.md`.

1. Benchmark Ollama on the iGPU, separate from `shared-ollama`:
   `docker network create bench-0006` then
   `docker run -d --name ollama-bench-0006 --network bench-0006 --device /dev/dri --group-add render --group-add video -e OLLAMA_VULKAN=1 -e OLLAMA_IGPU_ENABLE=1 -v ollama-bench-0006:/root/.ollama ollama/ollama:0.40.12`
2. Images and truth: the CORD-v2 test parquet unpacked to `$OUT/cord/NNN.jpg` + `NNN.json` (`gt_parse`).
3. Runner images: `bench-runner-0006` (python:3.11-slim + Pillow), `bench-donut-0006` (+ CPU Torch, transformers 4.46.3, sentencepiece).
4. `OUT=/path LIMIT=50 bench/run_all.sh`, then `python -I bench/score.py --truth $OUT/cord $OUT/*.jsonl`.

Gemini's free tier allows 20 requests a day; a benchmark run uses the production key's quota.

## Fallback scheduling study (WORK-0035)

`DATA=/absolute/cached/cord OUT=/absolute/private/run bench/run_fallback_schedule.sh`
freezes 30 test cases from IDs 050–099 (seed 35), keeping the earlier 000–049
benchmark separate. Use a new dedicated output directory outside Git. It uses
the current local models and read-only OCR cache, four CPUs/4 GiB, and no cloud
credentials. It neither reconfigures nor restarts production. Models are shared
with production; host/model contention is a measurement limitation.

Each selected receipt gets a full primary-stage capture and full fallback-stage
capture. Stage order alternates; failed/missing cases stay in the fixed truth
population. A confirmed container OOM is recorded as a failure before later work
continues in a fresh process. The harness never turns a retried failure into a
successful scored capture. Non-OOM process failures stop for inspection. The
whole pipeline cannot be claimed continuously available across these restarts.

In the parser image with `bench/`, data and outputs mounted, run
`python -m bench.fallback_schedule --data /data --out /results/capture --summarize`
for offline 60/50/45/40-second cutoff replays, then `--validate` for real serial
60/50/40-second schedules on the three slowest primary cases plus one observed
nonfatal primary failure, if any. Validation selection uses timings/errors, not
correctness labels; it is a stress check, not another independent accuracy set.

Replays assume standalone stage times transfer after cancellation; actual abort,
queue and shared-host effects can violate that assumption. The conditional
all-primary-stalled output is explicitly hypothetical, not a measured failure
rate. Both the existing CORD comparator (1% and thousand-scale ambiguity) and
strict numeric exactness are reported. CORD lacks merchant/date labels; public
model-training overlap is unknown. No profile, partial-result or timing policy
is promoted automatically from these outputs.
