---
id: 0023
title: "Preserve receipt totals when bounding OCR context"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0023 — Preserve receipt totals when bounding OCR context

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/llm_service.py:17,71-76,255`.

The fallback discards everything after the first 4,000 characters. Long receipts normally put totals, tender and date near the footer, so required evidence can be removed before inference. The fixed 1,536-token context also has to fit instructions and output; a character cap is not a token budget.

Synthetic OCR input with 500 item lines and a unique footer `TOTAL 123.45` produced a model prompt without that footer. This is confirmed loss of evidence; a real-model error rate was not measured here.

## Decision

Implemented: Budget tokens for instructions, text and output. Preserve header and footer evidence explicitly; use structured chunking for long item sections or report incomplete extraction. Make the context/output limits configurable and detect overflow instead of silently losing totals.

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

- [x] A receipt longer than the limit retains the unique footer total and header merchant in extraction input.
- [x] Long items are either fully processed or explicitly reported incomplete.
- [x] Prompt plus reserved output fits the configured context.

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
