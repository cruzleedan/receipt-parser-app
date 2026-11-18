---
id: 0035
title: "Evaluate the fallback reserve against measured full-extraction latency"
status: shipped
kind: spike
opened: 2026-11-17
decided: 2026-11-18
branch: spike/0035-fallback-reserve
supersedes: ~
superseded-by: ~
---

# WORK-0035 — Evaluate the fallback reserve against measured full-extraction latency

## Problem

WORK-0032 measured the corrected full OCR/text fallback at 16.49 seconds on the public sample and 26.52 seconds on a fictional 12-item receipt on CPU (15.62/22.32 seconds on GPU). The production VLM can consume 60 seconds of the 70-second request budget, leaving ten seconds. That reserve does not generally allow a full fallback to finish after primary timeout. Early primary failures still leave sufficient time; deadline enforcement is correct and bounds the final response.

Simply reserving 30 seconds would also cut the stronger VLM off at 40 seconds. Two of eight successful 1280 baseline receipts in this development run took 47.74 and 53.21 seconds. Previous benchmarks show that the fallback is substantially less accurate. No reserve value is therefore an evidence-free improvement, and the current primary budget has been preserved.

## Decision

Accepted: compare the current schedule against bounded alternatives on a larger, independently labelled local evaluation set. Consider a field-only fallback only when the caller explicitly requested that profile, adaptive reserves from measured output requirements, or an explicit partial-result contract. Keep the 70-second request ceiling and caller-requested fields. Do not silently skip items or shorten the primary budget without measuring resulting accuracy, timeout rate and latency.

## Options considered

| Option | Benefit | Cost | Chosen? |
|---|---|---|---|
| Keep 60 s primary / 10 s best-effort fallback | Preserves successful slow VLM answers | Late full fallback often cannot finish | Current behavior |
| Larger fixed fallback reserve | More fallback completions | Sacrifices stronger primary answers | Evaluate |
| Profile-aware/adaptive policy | Could allocate time to required fields | Needs calibration and a clear partial-result contract | Evaluate |

## Consequences

**Positive:** scheduling decisions would rest on end-to-end accuracy and deadline results, not only individual-stage timings.

**Trade-offs:** more local evaluation time and fresh labels; no policy has yet shown an overall improvement. No cloud service or paid model is required for the proposed experiment.

## Definition of done

- [x] Current timing distribution and timeout/fallback success measured on independent labels.
- [x] Candidate schedules compared with fixed eligible populations, including primary wins lost to earlier cutoff.
- [x] Profile/partial-result behavior remains explicit to callers and preserves the 70-second ceiling.
- [x] Adopt a demonstrated improvement or document why current scheduling remains preferable.

## Log

- 2026-11-17 proposed — additional performance finding from real fallback checks; no budget policy change made because the primary accuracy/latency tradeoff is unmeasured.

- 2026-11-18 building — owner approved "proceed with work 0035". Freeze a larger sample from cached CORD test IDs 050–099, excluded from all prior cached run IDs 000–049; measure local full primary and fallback with fixed settings. CORD provides independent human labels for amounts/items only, not merchant/date. Compare bounded schedules using explicitly labelled timing replay and targeted actual schedule checks. Existing owner-labelled cases remain development-only stress evidence. No model, output profile, API contract or production budget change without demonstrated benefit. "What's next" refers to this agent's tasks, not delegated Flutter work.

- 2026-11-18 resource finding — first isolated run exited 137 after five complete receipts. A fresh 4 GiB reproduction on the next fallback stage confirms Docker OOMKilled=true (12.58 s from attempt start). Record that stage as a failure, preserve all 30 IDs and continue remaining stages in fresh bounded containers after a kill; do not drop or retry failed cases in the scored dataset. Peak-memory policy is separately proposed WORK-0036. No production limits/config changed; production remains healthy. Restarted-process timings and missing captures will be reported explicitly, not presented as uninterrupted availability.

- 2026-11-18 measured — 30 frozen held-out CORD IDs, no input-hash overlap with the earlier 50; exactly 60 unique primary/fallback stage records. Two receipts lack total labels (28 eligible totals); merchant/date/currency truth unavailable. One input exceeds the existing byte limit; no outcome-based exclusion. Primary: 28 answers, 26/28 scale-tolerant totals, 22/28 strict numeric totals, item F1 .839, median/p95 11.49/21.97 s. Standalone fallback: 27 answers, 17/28 tolerant totals, 15/28 strict, F1 .470, median/p95 12.73/30.69 s; two confirmed memory-killed stages. All failures retained. Private metadata/answers remain outside Git under runs-0035/heldout30.

- 2026-11-18 compared — counterfactual 60/50/45/40 s primary-cap replays all yield 29/30 responses, 27/28 tolerant totals, 23/28 strict totals, item F1 .847, median/p95 11.56/21.97 s. One early primary extraction error is rescued by fallback; no primary timeout observed. Conditional assumed-stall replays are explicitly hypothetical, not a measured failure rate. Historical owner-development primary successes at 47.74/53.21 s demonstrate earlier-cutoff risk and are not mixed into the independent population. Full method, limits and results: [study report](../reviews/2026-11-18-fallback-reserve-study.md).

- 2026-11-18 actual validation — 12 actual full-profile scheduler calls: 60/50/40 caps on three slowest captured primary cases plus one nonfatal primary failure. Every cap returned 4/4 answers (three VLM, one fallback) and 4/4 strict correct totals; maximum elapsed 26.04 s. Timing/error-selected stress subset, not an independent accuracy estimate. Nine new deterministic regressions added; full unit suite 94 passed. No caller profile change, hidden item dropping, partial-result contract or total-deadline change.

- 2026-11-18 decision — retain current 60/10 scheduling. New independent amount/item evidence shows no improvement from shortening primary; there are no new merchant/date labels or actual timeout-rescue observations to establish target-domain benefit. More reserve cannot solve the measured fallback memory kills. WORK-0036 is proposed separately, without silently changing OCR sizing, production RAM or worker design. This spike completes with a no-promotion decision and reproducible tools; no parser deployment is needed because runtime source/configuration is unchanged.

- 2026-11-18 shipped — completed the spike with no production scheduling change. Final local unit suite 94 passed and production integration suite 4 passed; context, Python/shell syntax and whitespace checks pass. Integration runner now mounts bench read-only so the new benchmark regression module can be collected; the documented unit command includes that mount too. Logs `/tmp/parser-0035-unit-final.log` and `/tmp/parser-0035-live.log` are local/ephemeral. Measurement and validation containers are removed after preserving private attempt/exit records. No receipt/model data committed, paid API call, model download, runtime deployment or hosted Actions change. The owner's "what's next" preference is recorded in AGENTS.md; the next parser finding is proposed WORK-0036, not delegated Flutter work.
