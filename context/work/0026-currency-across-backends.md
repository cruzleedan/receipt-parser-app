---
id: 0026
title: "Extract and normalize currency in fallback and Gemini backends"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0026 — Extract and normalize currency in fallback and Gemini backends

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/llm_service.py:_build_prompt/_parse_response; src/gemini_service.py:_build_prompt/_parse_response; src/vlm_service.py:to_receipt`.

WORK-0014 added a currency field and normalization for the VLM only. The fallback and Gemini prompts never ask for currency, and their parsers construct ReceiptData without calling normalise_currency. Switching backend can lose a clearly printed currency; if a model volunteers a symbol or invalid code, those paths can return it unchanged. The API contract should not change depending on whether fallback ran.

## Decision

Implemented: Ask for currency in every backend and apply the existing conservative normalization rules to every parsed answer. Keep null for ambiguous symbols and receipts without currency, respecting the WORK-0014 decision.

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

- [x] Stubbed VLM, text and Gemini answers yield the same result for PHP, ₱, US$, bare $, invalid code and missing currency.
- [x] Both legacy prompts ask for printed currency without assuming a locale.

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
