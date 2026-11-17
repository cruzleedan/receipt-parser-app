---
id: 0024
title: "Remove the largest-total heuristic from fallback and Gemini prompts"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0024 — Remove the largest-total heuristic from fallback and Gemini prompts

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/llm_service.py:199-200; src/gemini_service.py:221-222`.

These prompts tell the model to look for the largest total near the bottom. For `TOTAL 80 / CASH 100 / CHANGE 20`, the largest monetary figure is tendered cash. The VLM already has an explicit amount-due rule excluding tender, change and VATable values, but the other backends retain the weaker instruction. This creates backend-dependent total semantics precisely when the primary has failed.

Evidence is the conflicting prompt text; this review did not run a real-model adversarial accuracy benchmark.

## Decision

Implemented: Use the same amount-due/tender/change distinction across backends, sharing field rules where practical. Include inclusive VAT, discounts, refunds and multiple TOTAL labels in the evaluation fixtures; do not replace one magnitude heuristic with another.

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

- [x] All backend prompts define total consistently and exclude tender/change explicitly.
- [x] Public or synthetic adversarial receipts are evaluated before deployment; aggregate results are recorded.

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
