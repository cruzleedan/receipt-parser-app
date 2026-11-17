---
id: 0019
title: "Make readiness and Docker health reflect unavailable models"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0019 — Make readiness and Docker health reflect unavailable models

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/main.py:119-150; src/llm_service.py:124-127; compose.yml:healthcheck; docker/Dockerfile:HEALTHCHECK`.

Overall health checks the text backend status but ignores `model_available`. The text service also accepts any tag whose name starts with the model family, so a different tag can look available. Separately, `/health` returns HTTP 200 for degraded and unhealthy results; both Docker health checks only use `curl -f`, so a quickly returned failure body still passes.

Synthetic ASGI probe with a ready VLM and text health `{status: connected, model_available: false}` returned `status: healthy`. These failures undermine automated readiness and hide broken fallback availability.

## Decision

Implemented: Define liveness versus readiness, including whether loss of a fallback alone should degrade readiness. Report exact configured model availability (with deliberate default-tag normalization). Have a readiness endpoint or probe exit nonzero for the defined failure states. Preserve the monitoring response contract deliberately.

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

- [x] Tests cover missing model, wrong tag, stopped Ollama, primary failure and fallback-only failure.
- [x] Docker health distinguishes the chosen ready and not-ready states.

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
