---
id: 0020
title: "Bound work that survives cancelled parser requests"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0020 — Bound work that survives cancelled parser requests

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P1 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/main.py:179,362-365; src/vlm_service.py:232; src/gemini_service.py:87-90; src/llm_service.py:89`.

Cancelling `asyncio.to_thread` stops awaiting the result; it does not stop the running synchronous OCR or HTTP call. There is no application admission limit or dedicated bounded worker ownership. New requests can start work while timed-out work still occupies CPU, threads or model queues. A requests timeout is also an inactivity timeout, not a total execution limit.

Synthetic ASGI probe: after a 0.03-second deadline returned 504, a 0.18-second OCR stub was still active. A second upload returned 504 with two OCR executions overlapping. This demonstrates retained work, not a claim that production PaddleOCR has already corrupted memory.

## Decision

Implemented: Add bounded admission and a bounded execution model. Use cancellable async network I/O; for CPU OCR use isolated workers or keep the capacity slot owned until the actual job completes. Do not merely wrap `to_thread` in a semaphore that is released on coroutine cancellation. Include queue wait in the deadline and return an explicit overload response.

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

- [x] Repeated timed-out requests cannot create unbounded active work or backlog.
- [x] Concurrency tests measure actual worker completion after cancellation.
- [x] Health remains responsive and overload responses are predictable.

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
