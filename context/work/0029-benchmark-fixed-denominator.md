---
id: 0029
title: "Count missing labelled receipts as benchmark failures"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0029 — Count missing labelled receipts as benchmark failures

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `bench/score_labels.py:40-44`.

The scorer skips labels absent from a run before incrementing n. An interrupted run containing only its easy successes can therefore appear more accurate than a complete run, undermining model and prompt selection.

Synthetic labels for r000 and r001 plus a run containing only correct r000 produced `labelled=1`, total/date/merchant/all-three=100%, and no-answer=0. It should expose 1/2 coverage and not rank this as complete 100% accuracy. Existing tolerances are documented choices and are not classified as bugs here.

During implementation, the shared benchmark amount normalizer also proved to strip minus signs from string amounts and accept non-finite numbers. It now preserves refunds and rejects invalid amounts, so exact-total scoring cannot crash on Infinity or silently score a negative label as positive.

## Decision

Implemented: Use one fixed eligible label population per comparison, count absent answers as missing/failure, and report coverage separately. Reject duplicate IDs or surface them explicitly. If subset evaluation is wanted, require an explicit common subset and print it.

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

- [x] The two-label, one-answer fixture reports 50% all-three and one missing answer.
- [x] Interrupted and full runs share a denominator; explicit subset behavior is tested.

- [x] Signed string totals retain their sign; boolean and non-finite benchmark values are rejected.

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
