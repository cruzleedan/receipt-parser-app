---
id: 0036
title: "Bound OCR memory on accepted receipt images"
status: proposed
kind: fix
opened: 2026-11-18
decided: ~
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0036 — Bound OCR memory on accepted receipt images

## Problem

WORK-0035's isolated, production-shaped benchmark (four CPUs / 4 GiB) was killed
with exit 137 after five completed public CORD receipts. A fresh process resumed
the next fallback stage and reproduced it; Docker explicitly reports
`State.OOMKilled=true`. Production stayed healthy and was not restarted. This
is a measured fallback availability problem in a separate benchmark, not proof
of a production incident. Exact input hashes, attempts and exit state remain in
`/home/dan/receipt-bench/runs-0035/heldout30/`, outside Git.

Accepted byte/pixel input bounds do not prove OCR's intermediate memory fits the
container. A Python timeout cannot reclaim memory from a still-running native
job. Reserving more fallback time cannot rescue a process killed for memory.

## Decision

Proposed: reproduce the accepted-image workload with memory telemetry, determine
whether peak allocation or retained shape caches dominate, then bound OCR memory
with a measured policy. Consider isolated OCR workers, input constraints or
explicit resizing only with accuracy and profile tests. Do not silently crop,
drop items, raise production RAM limits or change the model under WORK-0035.

## Definition of done

- [ ] Reproduce peak/retained OCR memory on fixed public inputs under production limits.
- [ ] Implement a measured bound with explicit image/accuracy semantics and deadline/admission behavior.
- [ ] Regression tests cover memory-failure recovery without duplicate or overlapping inference work.
- [ ] Candidate and authorized production verification record memory, quality and rollback evidence.

## Log

- 2026-11-18 proposed — concrete finding during WORK-0035; original process exited 137, fresh reproduction confirms Docker OOM kill. No production change authorized by this record.
