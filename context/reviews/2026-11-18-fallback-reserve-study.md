# WORK-0035 — Fallback reserve study, 2026-11-18

## Decision

Retain the current 60-second primary / ten-second best-effort fallback schedule
within the unchanged 70-second request deadline. No candidate demonstrated an
improvement on the new sample. This is a conservative no-promotion decision,
not evidence that 60/10 is universally optimal. Fix the separately recorded OCR
memory problem (WORK-0036) before promoting a larger fallback reserve.

No production code/configuration, requested fields, model, client/API contract
or partial-result policy changes. Full extraction remains the default. A caller
can still explicitly request the existing reduced field profile; the scheduler
does not silently select it.

## Population and method

Thirty public CORD-v2 test receipts were selected before inference from cached
IDs 050–099 with seed 35. All earlier cached benchmark runs used only 000–049;
the selected input hashes are unique and have no byte-identical overlap with
those 50. This is a development-held-out sample with independently supplied
human amount/item labels. Public-model training overlap is unknown, and CORD's
Indonesian layouts are not a representative independent sample of the owner's
mobile receipt population. Merchant/date/currency truth is unavailable.

The sample stays fixed at 30, including one input over the existing 10 MiB
limit. None exceeds 24 million pixels. Total labels exist for 28 cases; item
scoring has 73 labelled name/price pairs. Missing/failed answers stay failures.
No image or raw answer is committed. Hashes, selection, model/source identities,
raw answers, process attempts and exit states are in the private local
`/home/dan/receipt-bench/runs-0035/heldout30/` directory.

Each image received both a primary and a full OCR/text fallback capture, with
stage order alternating. Settings match production: 1280 VLM long side,
8192/2048 context/output, four CPU cores and a 4 GiB parser limit; text inference
uses explicit CPU placement, 12288/2048 context/output. Primary capture gets up
to 60 seconds including image preparation; each isolated fallback capture gets
up to 70 to measure how much reserve it would require. Primary model is
qwen3.5:4b (digest prefix d8b0f5e9760c), Ollama 0.40.12; fallback is
llama3.2-gpu:latest (a83e1ab27aff), shared Ollama 0.15.1, on CPU. Python 3.11.18,
PaddleOCR 3.3.0, httpx 0.28.1, Pillow 13.0.0 and pydantic 2.14.3 were recorded.
Models were not evicted or changed and no cloud/paid calls were made. Host and
model services remained shared, so contention and cache state are limitations.

The first process exited 137; a fresh reproduction confirmed an OOM on the next
fallback image. A later distinct fallback also caused a confirmed OOM. Both
scored failures remain failures. Only later unprocessed work resumed in fresh
bounded containers; the frozen population has exactly 60 unique stage records.
These captures do not establish continuous service availability across process
restarts. Their memory failures cannot be fixed merely by extending a timeout.

## Observed standalone stages

Timings include image loading/preparation and extraction, excluding one-time
service construction. Percentiles use nearest rank and include failed/rejected
attempt durations; successful-only timing is not substituted.

| Stage | Successful / 30 | Total, CORD comparator / 28 | Strict numeric total / 28 | Item F1 | Median s | p90 s | p95 s |
|---|---:|---:|---:|---:|---:|---:|---:|
| VLM primary | 28 | 26 | 22 | 0.839 | 11.49 | 17.34 | 21.97 |
| Full OCR/text fallback | 27 | 17 | 15 | 0.470 | 12.73 | 20.64 | 30.69 |

The primary had one extraction ValueError and the shared oversized-input
rejection, with no observed primary timeout. Fallback had two memory kills and
the oversized-input rejection, with no observed fallback timeout under its
isolated 70-second allowance. The maximum successful primary was 32.95 seconds.
A 200-like completed answer is distinct from a correct total or complete items.

The existing CORD comparator accepts 1% amount tolerance and the dataset's
ambiguous thousand-scale reading (e.g. 60 versus 60000). Strict numeric exactness
within 0.005 is reported separately, without accepting that scale difference.
Item matching uses the existing price comparator plus name similarity >= 0.6,
with one-to-one matches; it is not an exact item-name accuracy measure.

## Schedule replays

These are counterfactual serial timing replays, not 120 measured endpoint calls.
A valid primary answer within the cutoff wins; an early extraction failure
leaves the actual elapsed remainder for fallback. Otherwise fallback must fit
inside 70 seconds. Fatal input/process failures are not "rescued" by pretending
the same dead process could run another backend. The model assumes standalone
stage durations transfer after cancellation; queueing, native-worker ownership,
server cancellation and cache effects can break that assumption.

| Primary cap / reserve s | Results / 30 | Correct totals / 28 | Strict totals / 28 | Item F1 | Median / p95 s | Earlier primary successes lost |
|---|---:|---:|---:|---:|---:|---:|
| 60 / 10 | 29 | 27 | 23 | 0.847 | 11.56 / 21.97 | 0 |
| 50 / 20 | 29 | 27 | 23 | 0.847 | 11.56 / 21.97 | 0 |
| 45 / 25 | 29 | 27 | 23 | 0.847 | 11.56 / 21.97 | 0 |
| 40 / 30 | 29 | 27 | 23 | 0.847 | 11.56 / 21.97 | 0 |

All four use 28 primary answers and the same one early-error fallback answer.
The remaining case is the oversized-input rejection. No candidate wins or loses
on total accuracy in this held-out replay. No actual 60-second primary stalls
were observed, so these data do not estimate gains on that unobserved event.

A separate, explicitly hypothetical stress replay assumes every otherwise
accepted primary stalls. It shows why reserve might matter, without estimating
how often that condition occurs:

| Primary cap / reserve s | Fallback answers / 30 | Correct totals / 28 | Strict totals / 28 |
|---|---:|---:|---:|
| 60 / 10 | 8 | 4 | 3 |
| 50 / 20 | 22 | 12 | 10 |
| 45 / 25 | 25 | 15 | 13 |
| 40 / 30 | 25 | 15 | 13 |

These conditional differences are not measured improvements to the live parser.
The memory failures and oversized input remain failures; some fallback jobs need
more than 30 seconds. More returned answers also does not imply primary-level
quality.

For the distinct historical eight-receipt owner-labelled development subset in
WORK-0032, successful primary calls at 47.74 and 53.21 seconds were both correct
on total. A 50-second cap would preempt one; 45/40 would preempt two. Those are
previously used development controls, not added to the independent CORD sample.
Replacement fallback correctness/timing on those same photos was not measured
here, so this is a cutoff-risk count rather than a claimed net accuracy loss.

## Actual schedule validation and release evidence

Actual `main._run_backends` calls were then run at 60/50/40-second caps on the
three slowest captured primary cases plus the one observed nonfatal primary
failure. Selection used timings/errors, not correctness labels. These four cases
are a stress validation subset, not an additional independent quality sample.
All calls used the unchanged full extraction options and a 70-second outer
wall-clock deadline.

| Primary cap s | Results / 4 | Primary / fallback | Strict totals / 4 | Median s | Maximum s |
|---|---:|---:|---:|---:|---:|
| 60 | 4 | 3 / 1 | 4 | 15.68 | 26.04 |
| 50 | 4 | 3 / 1 | 4 | 14.93 | 25.55 |
| 40 | 4 | 3 / 1 | 4 | 13.87 | 25.57 |

All repeated primary calls completed below the smallest cap. These small timing
differences are not evidence that changing a cap speeds an already-completed
primary; cache/load/order effects remain. The one early primary error fell back
successfully at every cap. No memory kill occurred during this 12-call subset.
No actual primary-timeout rescue was observed in either population.

The nine new regression cases cover early failure, cutoff/ceiling boundaries,
fixed-population missing rows and primary wins preempted by earlier cutoffs,
strict versus scale-tolerant totals, actual cancellation/profile preservation
for full and explicitly item-free requests, and recording confirmed OOM failures
once. They also prevent treating fatal ingress/process failures as same-request
fallback opportunities. The full local unit suite passed **94 tests**, with **four production
integration tests passing separately**. Production and model
configuration remain unchanged; this spike delivers measurement tools, evidence
and the no-promotion decision rather than a runtime release.

Reproduction is documented in `bench/README.md`; use a new private output root.
The helper records confirmed failed stages and resumes only later work, without
changing a scored failure to a successful retry. Production memory bounds and
whole-request/admission behavior must be tested separately under WORK-0036.
Larger reserves or adaptive policies still need independent target-domain
merchant/date labels and enough genuinely slow/failed primary cases to measure
net quality. No raw dataset or model answer is committed.
