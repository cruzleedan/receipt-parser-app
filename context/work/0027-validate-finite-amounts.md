---
id: 0027
title: "Reject non-finite and boolean amounts before returning receipts"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0027 — Reject non-finite and boolean amounts before returning receipts

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/models.py:ReceiptItem/ReceiptData; src/vlm_service.py:114-146; src/llm_service.py:292-301; src/gemini_service.py:_parse_response`.

The VLM numeric checks accept bool because it subclasses int; Python json.loads also accepts NaN and Infinity by default. ReceiptData float fields allow non-finite values and coerce boolean amounts. Invalid totals may therefore become 1.0 or survive validation and fail JSON response serialization instead of triggering fallback or a handled extraction failure.

Synthetic calls to `to_receipt` accepted True→1.0, NaN→NaN and Infinity→Infinity. The shared models also affect legacy backends.

## Decision

Implemented: Use shared before-validation that rejects bool and requires finite numbers for every money field. Treat invalid primary answers as extraction failures, preserving legitimate zero and negative amounts where the receipt represents a refund. Prevent non-standard JSON numeric constants from leaking into responses.

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

- [x] All backends reject boolean/NaN/infinite money in total and item fields with a handled outcome.
- [x] Zero, normal decimal amounts and permitted refunds remain valid.

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
