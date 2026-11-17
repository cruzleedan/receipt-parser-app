---
id: 0017
title: "Route batch receipts through the configured backend and deadline"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0017 — Route batch receipts through the configured backend and deadline

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P1 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/main.py:496-525`.

`/parse-batch` calls OCR and the text LLM directly. It never calls `_run_backends`, ignores `PARSER_BACKEND`, and supplies neither a deadline nor an outer timeout. Production single uploads use Qwen3.5 while batch uploads always use the substantially weaker fallback. With ten files, three 120-second attempts per file can occupy a request for roughly an hour plus OCR and retry sleeps.

Synthetic ASGI probe: `PARSER_BACKEND=vlm_ollama`, a VLM stub that raises if called, and a 0.03-second parse deadline still produce a successful batch response after 0.125 seconds from a 0.12-second fallback stub.

## Decision

Implemented: Extract a shared per-image orchestration function used by both routes. Give each batch receipt the configured deadline; explicitly define and bound the whole batch duration. Convert per-image handled errors into BatchResult failures and preserve partial results. Keep sequential execution until capacity limits are established.

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

- [x] Batch and single routes use the selected backend with identical extraction options and fallback order.
- [x] A slow batch receipt ends within its budget and later receipts have an explicit policy.
- [x] Batch tests cover VLM success, fallback, invalid images and timeout without real models.

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
