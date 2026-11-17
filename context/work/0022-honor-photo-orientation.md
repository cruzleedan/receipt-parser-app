---
id: 0022
title: "Apply EXIF orientation before image preprocessing"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0022 — Apply EXIF orientation before image preprocessing

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/utils.py:20-26; src/vlm_service.py:236-240; src/ocr_service.py:49-51`.

The common loader opens and converts pixels but never applies EXIF orientation. Vision preprocessing then writes a new JPEG without that orientation metadata. A camera photo stored sideways with an EXIF rotation reaches the model sideways; the fallback also disables document/text orientation processing.

Synthetic JPEG with orientation 6 and stored dimensions 40×20 was returned by the loader as 40×20 instead of the upright 20×40.

## Decision

Implemented: Apply Pillow ImageOps.exif_transpose once in the common loader before normalization, then validate/decode. Use the same orientation policy in benchmark input preparation so comparisons match deployment.

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

- [x] Synthetic orientation 1, 3, 6 and 8 fixtures produce correctly oriented pixels.
- [x] Normal images and already upright images are not rotated twice.

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
