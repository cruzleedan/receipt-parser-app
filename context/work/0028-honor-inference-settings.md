---
id: 0028
title: "Honor inference settings and decouple OCR from text-model GPU selection"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0028 — Honor inference settings and decouple OCR from text-model GPU selection

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/llm_service.py:251-258; src/config.py:ollama_*; src/ocr_service.py:__init__; compose.yml:environment`.

The text request hardcodes temperature=0, top_p=0.9 and num_predict=768 instead of the exposed settings (defaults/top_p=0.8, num_predict=1024). More seriously, `num_gpu` is selected by OCR_USE_GPU. Production sets OCR_USE_GPU=false for CPU PaddleOCR and consequently forces shared Ollama text inference onto CPU (`num_gpu=0`) even though the model is named llama3.2-gpu. The OCR constructor itself only logs its use_gpu argument and never passes a device to PaddleOCR, so that setting is not a reliable device selector either.

This is visible in the constructed payload and constructor, not a measured production CPU/GPU utilization claim.

## Decision

Implemented: Read text sampling/output settings from Settings. Give text-model device/offload policy its own setting or allow Ollama automatic placement. Pass an explicit supported OCR device policy and report actual device information rather than the requested boolean. Benchmark the shared GPU impact before changing production placement.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Address the defect at its owning boundary | Explicit behavior and regression coverage | Implementation and validation effort | Yes |
| Keep current behavior | No immediate changes | Retains the failure described above | No |

## Consequences

**Positive:** corrects the documented failure and makes its behavior testable.

**Negative / Trade-offs accepted:** requires focused regression checks and candidate deployment validation; no production behavior changes are authorized by this proposal alone.

**Risks / Open questions:** coordinate shared pipeline and contract changes with related items in the [review report](../reviews/2026-11-17-code-review-and-research.md).

## Definition of done

- [x] Captured payload reflects overridden settings and changing OCR device does not change text offload.
- [x] OCR device selection is passed to the supported PaddleOCR API.
- [x] Fallback latency and contention are measured before rollout.

The default OCR device is now CPU, matching the pinned CPU Paddle wheel; explicit GPU configuration is still available with a compatible runtime. Compose preserves text CPU placement independently after the CPU/GPU comparison.

## Log

- 2026-11-17 proposed — code review; evidence and proposed remedy recorded, implementation deferred.

- 2026-11-17 building — owner: "proceed"; implementing review fixes and local, no-fee experiments.

- 2026-11-17 shipped — owner-authorized fixes and local study completed; 85 unit checks passed, final candidate and production integration checks each 4 passed. Parser image 56d70051e9b6; repository utilities covered by focused regressions; context validation passed.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead. Surface contradictions with an
> accepted, building, shipped or operating decision before proceeding.
