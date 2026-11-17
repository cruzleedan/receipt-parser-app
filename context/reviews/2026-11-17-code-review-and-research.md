# Code review and low-cost improvement research — 2026-11-17

Reviewed repository commit `813e330`. This review records 15 actionable findings: four P1, ten P2 and one P3. No syntax failures were found. Existing tests pass, but they do not exercise several backend, cancellation, readiness and long-receipt paths.

The initial review changed documentation only and proposed the work items. The owner subsequently authorized implementation; see the [implementation and experiment results](2026-11-17-implementation-and-experiments.md). At initial review time, no production settings, models, containers or application code were changed. Research used public primary sources; no private receipt photos or labels were opened or uploaded, and no paid API was called.

## Findings

P1 means address first because service responsiveness, capacity or the backend/deadline contract is affected. P2 means a concrete correctness or operational defect. P3 has limited current impact.

| Priority | Work item | Finding |
|---|---|---|
| P1 | [WORK-0017](../work/0017-batch-backend-and-deadline.md) | Batch bypasses the configured vision backend and has no parse deadline. |
| P1 | [WORK-0018](../work/0018-nonblocking-health-check.md) | Text-backend health performs blocking HTTP on the API event loop. |
| P1 | [WORK-0020](../work/0020-bounded-parser-workers.md) | Timed-out worker jobs continue running without admission/capacity bounds. |
| P1 | [WORK-0021](../work/0021-image-ingress-budget.md) | Upload/decode/preprocessing lack application limits and escape parts of the deadline. |
| P2 | [WORK-0019](../work/0019-health-readiness-contract.md) | Missing text models can look healthy; Docker ignores degraded/unhealthy response bodies. |
| P2 | [WORK-0022](../work/0022-honor-photo-orientation.md) | EXIF rotation is ignored before re-encoding camera photos. |
| P2 | [WORK-0023](../work/0023-preserve-receipt-footer.md) | First-4,000-character truncation removes footer totals; context budgeting is fixed. |
| P2 | [WORK-0024](../work/0024-fallback-total-semantics.md) | Legacy prompts favor the largest total, which can be tendered cash. |
| P2 | [WORK-0025](../work/0025-complete-line-item-extraction.md) | Legacy prompts silently limit extraction to ten products. |
| P2 | [WORK-0026](../work/0026-currency-across-backends.md) | Currency extraction and normalization are inconsistent across backends. |
| P2 | [WORK-0027](../work/0027-validate-finite-amounts.md) | Boolean and non-finite amounts pass numeric validation. |
| P2 | [WORK-0028](../work/0028-honor-inference-settings.md) | Exposed LLM options are ignored; CPU OCR also forces CPU text inference. |
| P2 | [WORK-0029](../work/0029-benchmark-fixed-denominator.md) | Missing labelled receipts disappear from benchmark accuracy denominators. |
| P2 | [WORK-0030](../work/0030-atomic-label-transactions.md) | Concurrent label saves can lose updates or race on the shared temporary file. |
| P3 | [WORK-0031](../work/0031-align-ocr-boxes-with-text.md) | Recognition text is paired with detection rather than recognition polygons. |

Each item has code locations, evidence, proposed design and acceptance checks. Static findings are distinguished from synthetic reproductions; prompt defects do not imply a newly measured real-model error rate.

## Verification

- Source-mounted unit suite in the existing parser image: **48 passed, 4 integration tests skipped**, 6.95 seconds. Skipped tests require PARSER_URL. The image was used for dependencies; the current checkout's src and tests were mounted read-only.
- Python AST parsing: **22 files passed** across src, bench, tests and test_api.py. Shell syntax checks passed for scripts, bench runners and quickstart.
- Synthetic ASGI/backend probes ran in an ephemeral container without network-connected model calls:
  - 150 ms blocking health GET delayed a 20 ms heartbeat to 170 ms.
  - Batch succeeded in 125 ms with a 30 ms deadline and did not call the configured VLM.
  - Health reported healthy with fallback model_available=false.
  - Two sequential requests returned 504 while their 180 ms OCR jobs overlapped (peak two active jobs).
  - A 5,012-character receipt lost its footer total in the fallback prompt.
  - True, NaN and Infinity were accepted as totals.
  - EXIF orientation 6 remained at stored dimensions 40×20 instead of upright 20×40.
- A synthetic scorer input with two labels and only one correct prediction reported 100% and no missing answers.
- Installed PaddleX source confirms that recognition filtering maintains rec_polys alongside rec_texts and rec_scores, whereas dt_polys includes rejected detections.

These checks establish code defects, not new production throughput or accuracy numbers. No live deployment test was needed for documentation changes. The suite emits existing deprecation warnings for Pydantic class Config/dict and FastAPI startup events; these were not promoted into speculative breakage findings.

## Existing evidence to preserve

The local project benchmarks are more relevant than a vendor's general OCR leaderboard:

- [WORK-0009](../work/0009-benchmark-on-owner-receipts.md): baseline Qwen3.5-4B led the tested alternatives on 58 readable owner-labelled receipts. Gemma, GLM-OCR, OvisOCR3 and the old two-stage pipeline were worse on key fields.
- [WORK-0008](../work/0008-vision-model-backend.md): deployed end-to-end results after prompt changes were approximately **84% total, 64% date, 90% merchant, 48% all three**, median **16.1 s**, p90 **38.9 s**. The separate prompt-only 84/71/91/57% run is a different result and should not be presented as production accuracy.
- [WORK-0010](../work/0010-existing-receipt-fine-tunes.md): NuExtract3 did not beat the tuned Qwen prompt locally.
- [WORK-0011](../work/0011-fine-tune-from-confirmed-receipts.md): consent-based data collection is already building; training waits for several hundred examples. Do not create a competing collection system.
- [WORK-0015](../work/0015-field-confidence-spike.md) and [WORK-0016](../work/0016-field-confidence.md): digit-token confidence is already implemented. Its thresholds need independent validation before driving retries. It is a model signal, not a calibrated probability that the field is correct.

## Ranked free or cheap improvements

The following are research recommendations, not measured improvements on this checkout. “Free” means no API or software fee; electricity, local memory, storage and engineering time still cost something. Implementation/experiments are tracked in [WORK-0032](../work/0032-low-cost-performance-accuracy-experiments.md).

| Order | Change or experiment | Expected benefit and practical limit | Incremental price |
|---|---|---|---|
| 1 | Fix ingress, worker capacity, blocking health and backend parity (0017–0021). | Protect p95/p99 latency and fallback availability under load. Does not by itself improve character recognition. | No API fee. |
| 2 | Fix EXIF, preserve footer evidence, remove misleading total/ten-item rules, normalize currency and money (0022–0028). | Recover avoidable errors with existing models. Measure each change separately. | No API fee. |
| 3 | Test image geometry: baseline 1280, 1600, 1920 long side; crop blank background; preserve receipt width; selectively re-read a high-resolution date/total region. | A very tall receipt shrinks to a narrow strip under the current square thumbnail limit: a 1000×6000 image becomes about 213×1280. Crops may retain small digits. More pixels/extra calls can increase latency and visual context. | Local compute only. |
| 4 | Add a field-only extraction profile and bounded selective re-read. | `items=false`, `subtotal=false`, `tax=false`, `time=false` is already available to callers. Generate merchant/date/total/currency only when that is all the workflow needs. Retry an uncertain field on its crop only if time remains. | No API fee; lower output may save time, retries add time. |
| 5 | Tune actual Ollama placement, output/context budgets and warm start; profile before changing runtimes. | Separate CPU OCR from text GPU settings. Keep the already-loaded VLM configuration; measure first-after-restart latency and consider preload. Test attention/cache settings only where this model, pinned runtime and Vulkan backend support them. | Local RAM/GPU memory and electricity. |
| 6 | A/B Qwen3.5-4B at higher weight precision and Qwen3.5-9B as a selective local escalation. | Plausible accuracy improvement, larger memory/latency cost; no receipt-specific win established. Loading a second model can evict the primary with MAX_LOADED_MODELS=1 and consume the fallback reserve. Test separately first. | No API fee; model storage and local compute. |
| 7 | Benchmark explicit lightweight OCR models for the fallback and evidence extraction. | Compare supported PP-OCRv5 mobile/server settings; PP-OCRv6 tiny/small/medium is a newer candidate requiring an isolated compatibility check with the pinned stack. OCR-only results still need extraction and date/total semantics. | No inference API fee; integration effort. |
| 8 | Optional paid cloud escalation for a small uncertain fraction, using public/consented samples only. | Potentially cheap, but accuracy on these receipts is unmeasured and it changes the current local-only decision. Require a separate decision before enabling or uploading. | Illustrative Gemini price below. |

### Why these directions are supported

**Image orientation and local preprocessing.** Pillow provides `ImageOps.exif_transpose` to apply camera orientation and remove the consumed tag. This directly addresses WORK-0022. Crop/resolution experiments are an inference from the current thumbnail geometry, not a vendor promise. Avoid blanket aggressive thresholding: it can erase faded thermal print. Compare minimally normalized input against optional transformations on a held-out set. [Pillow documentation](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose).

**Structured extraction.** Ollama supports passing a JSON schema and recommends validation against the response model. The VLM already uses schema output; replacing it with generic JSON would lose that constraint. Extend a shared field contract to the fallback and normalize answers consistently. A schema controls shape, not whether the printed amount was read correctly. [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

**Runtime tuning.** Ollama documents preloading, keeping models resident, bounded server queues and model concurrency. It also documents Flash Attention and quantized KV cache with backend/model compatibility requirements. Production already uses `keep_alive=-1` and one parallel request: those are existing choices, not proposed discoveries. Test options on the pinned runtime before adopting current-documentation advice; there is no measured 890M speedup here. [Ollama FAQ](https://docs.ollama.com/faq).

Capture `load_duration`, `prompt_eval_duration`, `eval_duration` and token counts from each inference, along with application queue/preprocessing time and selected backend. These distinguish cold starts, image processing, long outputs and queueing. Use aggregate measurements without receipt contents. [Ollama chat API](https://docs.ollama.com/api/chat).

**Model choice.** The official Qwen model card reports stronger general document/OCR scores for 9B than 4B (for example OCRBench 89.2 versus 85.0). Both have official model cards and Apache-2.0 licensing. This supports a candidate experiment, not extrapolation to Philippine receipt accuracy or a 70-second latency promise. Check local GGUF availability, actual RAM usage, quantization and warm/cold latency before choosing it. [Qwen3.5-4B card](https://huggingface.co/Qwen/Qwen3.5-4B), [Qwen3.5-9B card](https://huggingface.co/Qwen/Qwen3.5-9B).

**OCR alternatives.** Paddle's documentation exposes mobile/server OCR variants and their speed/accuracy tradeoffs. Its newer PP-OCRv6 documentation describes tiny/small/medium tiers; the paper reports substantial OCR gains and a faster tiny CPU tier on its own benchmark. These are vendor OCR measurements, not end-to-end receipt JSON accuracy on d3. Try only after the current fallback device/configuration defects are fixed; do not upgrade the pinned 3.3.0/3.2.0 stack in place as part of research. [PP-OCRv5 documentation](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html), [PP-OCRv6 documentation](https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/docs/version3.x/algorithm/PP-OCRv6/PP-OCRv6.en.md), [PP-OCRv6 paper](https://arxiv.org/abs/2606.13108).

**Cloud price illustration, checked 2026-11-17.** Google's standard Gemini 2.5 Flash-Lite table lists **$0.10 per million input tokens and $0.40 per million output tokens**. At an assumed **3,000 billed input tokens (including the image) and 500 output tokens**, that is **$0.0005 per receipt**, or **$0.50 per 1,000 receipts**. Escalating only 10% of 1,000 receipts would cost about **$0.05**, excluding retries and any additional billable tokens. These are token assumptions, not observed receipt usage. Free-tier content may be used to improve products; paid-tier content is marked otherwise. Prices, model lifecycle and quota must be rechecked before adoption; the repository's historical 20 requests/day is not a universal current allowance. [Google pricing](https://aistudio.google.com/docs/pricing#gemini-2.5-flash-lite).

### Experiment and adoption gates

1. Fix the scorer denominator (0029) before comparing incomplete runs. Freeze a production end-to-end baseline, backend identity, model digest/quantization, runtime version, prompt/schema, image settings and extraction options.
2. Reuse already authorized local labels only under their existing handling rules; do not assume retention, additional uploads or training consent. Never use cloud with the private benchmark corpus. Use public/synthetic receipts for cloud evaluation unless separately authorized.
3. Split development versus held-out evaluation by receipt/merchant and remove duplicates. The old 58 labels have been used for prompt selection; treat them as development evidence, not a fresh unbiased test. Add confirmed examples when available through WORK-0011, avoiding training/evaluation overlap.
4. Measure exact-to-currency-minor-unit totals alongside the historical 0.5% tolerance, normalized date exact match, merchant match, currency, line-item completeness/F1 and all-key-fields accuracy. Report blank/unreadable rejection, missing outputs, fallback frequency and confidence false negatives. Tax-inclusive receipts and discounts invalidate simplistic subtotal+tax rules, so arithmetic checks should flag disagreement rather than silently overwrite extracted evidence.
5. Report median/p90/p95, deadline miss rate, warm/cold timings and 1/2/4 concurrent request behavior. Count queue time in user-visible latency. Show paired wins/losses and uncertainty on small samples; do not announce a reliable gain from one or two extra correct receipts.
6. Sweep geometry/profile first, then precision/model/OCR. Change one factor at a time. Calibrate selective re-read thresholds on development data and evaluate once on held-out data, reserving the existing fallback budget. Never average disagreeing totals or silently choose a consensus as truth.
7. Promote a change only if held-out results improve the chosen accuracy/latency tradeoff, no required field silently disappears and the configured deadline remains respected. Preserve confirm-before-saving. Apply candidate and production integration checks only when an accepted implementation is deployed.

Recommended next decision: accept the four P1 fixes and the low-effort correctness fixes first; then authorize WORK-0032's local geometry/profile experiments. Continue WORK-0011 data collection. Defer paid training, runtime replacement and cloud escalation until the inexpensive experiments show what errors remain.

## Follow-up findings during implementation

- [WORK-0033](../work/0033-persist-ocr-model-cache.md): persist OCR model assets across container recreation.
- [WORK-0034](../work/0034-report-actual-backend.md): zero OCR time had been mislabelled as Gemini by the benchmark; record actual backend/model identity.
- [WORK-0035](../work/0035-evaluate-fallback-reserve.md): measured full fallback exceeds the ten-second late-fallback reserve; evaluate scheduling without prematurely cutting off stronger primary answers. This remains proposed.
