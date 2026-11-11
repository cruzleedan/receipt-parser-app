# Receipt-parsing benchmark (WORK-0006)

Scores receipt backends against CORD-v2 test ground truth. Results and method: `context/work/0006-local-vision-model-benchmark.md`.

1. Benchmark Ollama on the iGPU, separate from `shared-ollama`:
   `docker network create bench-0006` then
   `docker run -d --name ollama-bench-0006 --network bench-0006 --device /dev/dri --group-add render --group-add video -e OLLAMA_VULKAN=1 -e OLLAMA_IGPU_ENABLE=1 -v ollama-bench-0006:/root/.ollama ollama/ollama:0.40.12`
2. Images and truth: the CORD-v2 test parquet unpacked to `$OUT/cord/NNN.jpg` + `NNN.json` (`gt_parse`).
3. Runner images: `bench-runner-0006` (python:3.11-slim + Pillow), `bench-donut-0006` (+ CPU Torch, transformers 4.46.3, sentencepiece).
4. `OUT=/path LIMIT=50 bench/run_all.sh`, then `python -I bench/score.py --truth $OUT/cord $OUT/*.jsonl`.

Gemini's free tier allows 20 requests a day; a benchmark run uses the production key's quota.
