---
id: 0030
title: "Serialize label read-modify-write transactions"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0030 — Serialize label read-modify-write transactions

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | fix |
| **Priority** | P2 |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Location at review commit `813e330`: `bench/label_server.py:Handler.do_POST; bench/label_server.py:ThreadingHTTPServer`.

The threaded server reads all labels, changes one entry, writes the shared labels.tmp path, then replaces labels.json without a lock. Two saves can read the same old snapshot and overwrite one another. They also race on the same temporary path, so one replace can remove the other request's file and cause a server error. Atomic rename prevents partial file visibility but does not make the read-modify-write transaction atomic.

Confirmed by inspection; no user label files were opened or changed during review.

## Decision

Implemented: Serialize the entire read/modify/write transaction with a shared lock for this single-process tool, or use SQLite transactions if multiple processes are supported. Use unique temporary files and preserve atomic replacement; handle persistence errors explicitly.

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

- [x] Simultaneous saves for different IDs preserve both updates and return success.
- [x] Persistence failure leaves the previous complete label file intact.

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
