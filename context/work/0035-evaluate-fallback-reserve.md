---
id: 0035
title: "Evaluate the fallback reserve against measured full-extraction latency"
status: proposed
kind: spike
opened: 2026-11-17
decided: ~
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0035 — Evaluate the fallback reserve against measured full-extraction latency

## Problem

WORK-0032 measured the corrected full OCR/text fallback at 16.49 seconds on the public sample and 26.52 seconds on a fictional 12-item receipt on CPU (15.62/22.32 seconds on GPU). The production VLM can consume 60 seconds of the 70-second request budget, leaving ten seconds. That reserve does not generally allow a full fallback to finish after primary timeout. Early primary failures still leave sufficient time; deadline enforcement is correct and bounds the final response.

Simply reserving 30 seconds would also cut the stronger VLM off at 40 seconds. Two of eight successful 1280 baseline receipts in this development run took 47.74 and 53.21 seconds. Previous benchmarks show that the fallback is substantially less accurate. No reserve value is therefore an evidence-free improvement, and the current primary budget has been preserved.

## Decision

Proposed: compare the current schedule against bounded alternatives on a larger, independently labelled local evaluation set. Consider a field-only fallback only when the caller explicitly requested that profile, adaptive reserves from measured output requirements, or an explicit partial-result contract. Keep the 70-second request ceiling and caller-requested fields. Do not silently skip items or shorten the primary budget without measuring resulting accuracy, timeout rate and latency.

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

- [ ] Current timing distribution and timeout/fallback success measured on independent labels.
- [ ] Candidate schedules compared with fixed eligible populations, including primary wins lost to earlier cutoff.
- [ ] Profile/partial-result behavior remains explicit to callers and preserves the 70-second ceiling.
- [ ] Adopt a demonstrated improvement or document why current scheduling remains preferable.

## Log

- 2026-11-17 proposed — additional performance finding from real fallback checks; no budget policy change made because the primary accuracy/latency tradeoff is unmeasured.
