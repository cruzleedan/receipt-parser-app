# Review fixes and local experiments — 2026-11-17

Follow-up to the [code review](2026-11-17-code-review-and-research.md), implemented on `fix/0017-parser-review-fixes` after the owner's “proceed”. WORK-0017–0031 cover the original 15 findings; WORK-0033 and WORK-0034 record the additional cache/provenance problems found during implementation. WORK-0032 records the local experiments.

## Resulting behavior

- Both parse endpoints use the configured primary backend, shared fallback order, image preparation and extraction options. Every image has a deadline; a batch also has a 70-second total budget and preserves completed results.
- The default admission limit is one request. Extra requests get 503 with Retry-After. CPU work has one bounded worker, whose slot stays occupied until the actual job finishes even after a timeout. Network inference and health use cancellable async HTTP with wall-clock limits. Gemini uses its asynchronous SDK; no cloud backend was invoked during this work.
- Multipart ingress has size/time bounds before FastAPI parses files. Individual images have byte/pixel bounds, are eagerly decoded off the event loop, and consume the request deadline. EXIF orientation is applied once.
- All backends share field instructions, currency/date normalization and finite money validation. They preserve zero/refunds, exclude tender/change from total selection, and request every item. Text input is never silently truncated; over-budget text or token-truncated output produces a handled extraction failure. Unreadable dropped items carry extraction_warnings.
- `/health` retains HTTP 200 diagnostics; `/ready` returns 503 unless primary and fallback dependencies are available. Exact model tags matter. Docker probes readiness. Responses identify the actual answering backend and model.
- Text inference settings are honored. OCR is explicitly on CPU in production; text-model placement is independent. The application permits automatic placement; Compose explicitly preserves CPU placement after the measured tradeoff. The text context/output defaults are 12,288/2,048, with a conservative UTF-8 byte upper bound for input budgeting.
- Benchmark comparisons have a fixed label denominator, expose missing output, reject duplicate IDs, preserve signed totals and reject non-finite amounts. Label writes are serialized transactions with unique temporary files. OCR text uses recognition polygons.
- OCR model assets persist across container recreation. The model-cache volume was seeded from the working production assets; receipt input/output is not stored there. Parse-result retention remains disabled by default.

The [README](../../README.md) documents limits, response codes and configuration. Normal requests still extract their requested line items and optional fields. No automatic crop, resolution increase, selective retry, model switch or field-only default was enabled.

## Local experiment design

Eight receipts were selected deterministically with seed 32 from the existing, locally retained owner-labelled corpus before the comparisons. Input byte hashes, selected IDs, raw answers and run metadata are in the private `runs-0032` directory under the existing corpus, outside git. Nothing from that corpus was sent to a cloud model or viewed through an image tool.

These are **previously used development labels**, not fresh independent held-out data. One selected receipt has no valid date label: totals and merchant have eight labels, date/all-three have seven. All arms share those fixed eligible populations; a timeout remains a failure. Merchant matching uses the project's documented fuzzy criterion; totals use cent-exact comparison. Currency and line-item truth are unavailable for this corpus, so no accuracy is claimed for those fields here.

The corpus preparation already applied EXIF normalization and a 2,000-pixel long-side bound. Geometry results therefore do not measure EXIF correction or recovery from original full-resolution camera photos. Synthetic fixtures verify orientation separately.

All arms used the existing **Qwen3.5-4B Q4_K_M**, Ollama **0.40.12**, Vulkan on the Radeon 890M, 8,192 context, 2,048 output tokens, temperature zero, no thinking, schema output and log probabilities. Model digest/runtime/source hashes are frozen in private metadata. Arm order was interleaved by receipt to reduce ordering bias; the model was already warm. Background host services remained running.

Times below include VLM payload preparation, inference and answer validation; they exclude upload ingress and the OCR fallback. The primary call gets at most 60 seconds within a 70-second processing deadline, reserving ten seconds for fallback. Here a primary timeout is recorded directly rather than invoking the weaker fallback. Small-sample p90/p95 equal the maximum; these are descriptive figures, not reliable tail-latency estimates.

| Arm | Total exact | Date | Merchant | All three | Median s | p90 s | Primary timeouts |
|---|---|---|---|---|---:|---:|---:|
| Normal 1280 baseline | 8/8 | 5/7 | 8/8 | 5/7 | 23.23 | 53.21 | 0 |
| 1600 long side | 7/8 | 5/7 | 6/8 | 4/7 | 27.68 | 60.06 | 1 |
| 1920 long side | 6/8 | 4/7 | 6/8 | 4/7 | 30.98 | 60.06 | 2 |
| Field-only 1280 | 8/8 | 6/7 | 7/8 | 6/7 | 6.65 | 6.83 | 0 |
| White-border crop, 1280 | 8/8 | 5/7 | 8/8 | 5/7 | 26.39 | 58.15 | 0 |

The field-only profile disables items/time/subtotal/tax through existing query options and still extracts merchant/date/total/currency. Its median was about 71% lower, with one paired all-three win and no paired all-three losses; one merchant answer changed from correct to incorrect on the receipt without a date label. This is strong latency evidence for this smaller task, **not evidence that dropping requested fields is an equivalent replacement or that accuracy reliably improves**. One paired quality win among seven fully labelled examples is far too little for an accuracy claim.

A second-stage prototype flagged date/total fields below 0.9 token confidence or missing, then used a 1920 field-only header/footer re-read within the remaining primary budget. It flagged six receipts, made six additional calls, had two re-read timeouts, and changed no field. All-three remained 5/7; median rose to 26.72 seconds and p90 to 60.01 seconds. Original answers were preserved on re-read failure. One of two wrong dates with valid labels had confidence at least 0.9. There were no wrong baseline totals in this subset, so total-error detection sensitivity cannot be estimated.

**Decision:** retain 1280 and the current full extraction default. Document the existing field-only query for workflows that deliberately do not need items. Reject this simple white-border crop and confidence/header-footer retry policy for deployment. Do not calibrate or promote a retry threshold from eight already used receipts.

Larger/higher-precision models, a new OCR stack and attention/cache tuning are deferred: the cheap tested changes already identify output volume as a major latency factor, while stronger quality evidence and isolated memory/load tests are needed before changing a resident production model. Loading other models or forcing a true VLM cold start would also evict/interfere with the current primary. Existing negative keep-alive is preserved. Paid/cloud experiments and training remain unrun; WORK-0011 still waits for sufficient consented examples.

A point-in-time observation during this work was about 336 MiB for the parser (4 GiB limit) and 6.7 GiB for parser-ollama; this is not a measured peak or a claim about dedicated GPU memory. The OCR cache is about 93 MB. No paid API or model purchase was used.

## Reproduction

Run the helpers in the parser image, on its internal Docker networks, mounting source/bench read-only and the existing corpus read-only. Mount only a dedicated private output directory writable. `bench/optimize.py` runs the paired geometry/profile arms; `bench/selective_reread.py` consumes those results and evaluates the bounded prototype. Each produces aggregate summaries plus private per-receipt records. Reusing an output path appends records, so use a fresh output directory for a fresh run.

`bench/make_synthetic.py` renders a clearly fictional tender/change/VAT receipt with 12 products. `bench/check_fallback.py` compares old/new fallbacks on it and the public sample. `bench/check_capacity.py` checks 1/2/4 concurrent requests and readiness latency using only the public sample. These helpers never invoke a cloud backend.

## Real fallback checks

Both old and corrected pipelines used the existing 3.2B Q4_K_M text model on shared Ollama 0.15.1. These tiny fixture comparisons validate behavior; they are not a throughput study. Old/new code also differ in prompts, schema, context and output budget, so old-versus-new timing cannot isolate a GPU effect. A separate corrected-CPU pass provides the device comparison.

| Fixture / pipeline | Total | Items | End-to-end s |
|---|---:|---:|---:|
| Public sample, old CPU (first run) | 24.10 | 5 | 11.64 |
| Public sample, corrected GPU | 24.10 | 5 | 15.62 |
| Public sample, corrected CPU | 24.10 | 5 | 16.49 |
| Fictional 12-item receipt, old CPU (first run) | **100.00, wrong** | **1, incomplete** | 10.57 |
| Fictional 12-item receipt, corrected GPU | **80.00, correct** | **12, complete** | 22.32 |
| Fictional 12-item receipt, corrected CPU | **80.00, correct** | **12, complete** | 26.52 |

The repeat old-CPU control was 11.45/10.13 seconds and reproduced the same totals/item counts. The corrected GPU saved about 0.9/4.2 seconds relative to corrected CPU on these fixtures, while the server reported 10,190,434,304 bytes (about 9.5 GiB) of GPU allocation versus zero on CPU. **Production therefore preserves explicit CPU text placement**, independently of OCR. No GPU speedup is claimed as a deployed optimization. The corrected pipeline spends more time generating and validating a fuller answer; the faster incorrect old result is not an acceptable accuracy tradeoff.

The measured full fallback times also exceed the existing ten-second reserve after a 60-second primary timeout. Early primary failures still leave more fallback time; the whole request remains capped at 70 seconds. Automatically reserving 25–30 seconds would shorten the better primary's budget and cut off some successful baseline receipts (47.74/53.21 seconds here). This is an explicit unresolved scheduling tradeoff, recorded in WORK-0035; the current primary budget is preserved rather than making an unmeasured accuracy regression.

## Release and validation

Completed WORK-0017–0034; WORK-0035 remains **proposed** because changing the primary/fallback time split needs a separate accuracy comparison. The study did not promote a new model, resolution or correction policy.

- Final-image unit suite: **85 passed**, four live tests skipped in that run. The live suite was then run separately against the final candidate and production: **4 passed on each** (19.05 and 19.12 seconds respectively).
- Regression coverage includes cancellation/real worker ownership, async health/SDK cancellation, batch routing/fallback/deadlines, streamed byte and pixel limits, upload/preprocessing budgets, rotated JPEG pixels, long OCR evidence, 12-item cleaning, invalid money, currency, inference options, output truncation, nested NumPy polygon serialization, missing/duplicate benchmark output and concurrent/failed label persistence.
- Public-fixture capacity check: one successful parse at each of 1/2/4 concurrent uploads; excess calls returned 503 in 16–17 ms. Successful parses took 11.57–11.67 seconds, and readiness stayed at or below **38 ms** across 160 probes. This verifies bounded admission and responsiveness, not increased parallel inference throughput.
- Python/shell syntax, local documentation links, git whitespace and `scripts/verify-context.sh` checked. Existing FastAPI startup deprecation warnings remain; no runtime failure was observed.
- Production was recreated from the exact tested image, `receipt-parser-app-parser:review-final-20261117`, image ID `sha256:56d70051e9b6bbcb6e715ae81740e039f0377bf0c60620e37e7280cf21fc504e`. `/ready` and Docker health are healthy. Cached OCR asset reuse was observed after recreation. Temporary candidate/fallback test containers were removed afterward.
- No commit, push, private image upload, paid API call or model download was performed. Source and work items remain reviewable on `fix/0017-parser-review-fixes`. Raw corpus/results stay in the private local benchmark directory.

Rollback image: `receipt-parser-app-parser:rollback-pre-review-20261117`. Use a Compose override that selects that image and restores its `/health` Docker probe (the old code has no `/ready`):

```yaml
services:
  parser:
    image: receipt-parser-app-parser:rollback-pre-review-20261117
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
```

Then run `docker compose -f compose.yml -f /path/to/rollback.yml up -d --no-deps --no-build parser`. The cached OCR assets remain compatible. Current integration tests assert the new backend metadata, so a rollback check must use the prior tests from `813e330` or explicitly validate the legacy response contract.

## Source publication follow-up — 2026-11-17

Owner explicitly requested publishing and merging the parser source after the
expense-api WORK-0087 rollout. Fresh publication checks passed: 85 unit tests,
four live production integration tests, context validation and whitespace checks.
All 15 local `src/**/*.py` files match the running `56d70051e9b6` image by SHA-256.
The service is healthy; publication changes no parser runtime configuration or
model and requires no redeployment. Earlier statements about uncommitted source
record the state at their original verification time. WORK-0035 remains proposed.
No private receipt, label, raw answer, credential or benchmark output is included.

The owner confirmed that local builds/tests/deployments are the intended way to
avoid hosted CI costs. Read-only repository inspection found expense-api Actions
disabled; parser repository Actions enabled but no workflow files. No setting
was changed and no hosted workflow was introduced. Use the documented local test,
context and deployment commands; absent hosted checks are expected. Re-enabling
expense-api Actions or adding hosted parser automation needs a separate request.
