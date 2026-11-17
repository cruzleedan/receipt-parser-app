---
id: 0021
title: "Bound image ingestion and include preprocessing in the request budget"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0021 — Bound image ingestion and include preprocessing in the request budget

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P1 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `src/main.py:338-364,479-484; src/utils.py:20-26; src/vlm_service.py:235-241`.

Both routes read the entire upload without an application byte limit. There is no explicit decoded-pixel budget. Pillow supplies a large-image warning/error threshold, but ordinary images below that threshold can still consume substantial memory in a 4 GB parser container. File opening/conversion and VLM RGB conversion, resizing and JPEG encoding run synchronously on the event loop. `/parse` starts its enforced timeout only after image loading, so its documented whole-parse deadline excludes earlier work and cannot preempt synchronous preprocessing.

This is a resource and latency defect even for an internal service receiving accidental large camera scans. No large allocation or live load test was performed.

## Decision

Implemented: Set configurable per-file byte and pixel limits, enforce upload limits while reading (and at the upstream ingress for multipart spooling), reject oversized input with a handled response, and eagerly validate/decode within a bounded worker. Start the processing budget before upload consumption and charge preprocessing and queue time to it. Document that ASGI multipart parsing occurs before route execution and needs an ingress-level bound.

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

- [x] Oversized bytes and dimensions get explicit handled errors for single and batch requests.
- [x] Near-limit decoding does not block health; corrupt/truncated RGB images get a client error.
- [x] A preprocessing delay consumes the same processing deadline.

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
