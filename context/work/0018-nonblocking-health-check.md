---
id: 0018
title: "Remove blocking network I/O from the health coroutine"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0018 — Remove blocking network I/O from the health coroutine

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P1 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/llm_service.py:110-118`.

`OllamaLLMService.health_check` is async but performs `requests.get(timeout=5)` directly. `/health` invokes it on the only API event loop, including every Docker probe. An unresponsive shared Ollama can pause every request and prevent the event loop from delivering parse deadlines on time.

Synthetic probe: a 150 ms stubbed GET delayed a concurrent 20 ms heartbeat to 170 ms. Existing health tests replace the entire health coroutine, so they miss this path.

## Decision

Implemented: Use an asynchronous HTTP client with bounded connect/read/total budgets, or move this request off the event loop as an immediate fix. Run independent backend probes concurrently within one health budget.

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

- [x] A deliberately slow shared-Ollama health probe does not delay an event-loop heartbeat or a parse timeout.
- [x] The real health implementation is exercised with a stubbed HTTP transport.

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
