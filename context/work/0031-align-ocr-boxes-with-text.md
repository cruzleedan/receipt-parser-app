---
id: 0031
title: "Pair recognized text with recognition polygons"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0031 — Pair recognized text with recognition polygons

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P3 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/ocr_service.py:86-95,170-181`.

The adapter pairs filtered rec_texts/rec_scores with dt_polys by index. The installed PaddleX OCR pipeline keeps dt_polys for all detections and appends rec_texts, rec_scores and rec_polys only for accepted recognition results. If the first detection is filtered out, the first accepted text gets the first rejected detection's coordinates. Current receipt extraction uses full_text, so the immediate impact is incorrect OCRResult.boxes and future spatial consumers rather than changed totals.

Verified against the installed image's `paddlex/inference/pipelines/ocr/pipeline.py` (recognition filtering around lines 453-467).

## Decision

Implemented: Use aligned rec_polys for accepted recognition output; validate lengths and retain detection-only polygons separately if needed. Do not rely on equality of detection and recognition counts.

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

- [x] A fixture with one rejected detection pairs surviving text with its own polygon and score.
- [x] Empty recognition and mismatched lengths are handled deliberately.

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
