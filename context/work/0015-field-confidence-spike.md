---
id: 0015
title: "Spike: which read fields to flag for a second look"
status: building
kind: spike
opened: 2026-11-12
decided: 2026-11-12
branch: spike/0015-field-confidence
supersedes: ~
superseded-by: ~
---

# WORK-0015 — Spike: which read fields to flag for a second look

| | |
|---|---|
| **Opened** | 2026-11-12 |
| **Status** | building |
| **Kind** | spike |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

expense-api IDEA-0012: the review shows every read field the same way, so people cannot tell which to check. On the owner's labelled receipts (WORK-0009) about a third of dates and a sixth of totals are wrong.

## Decision

Research only. Measure, on the owner's labelled receipts and only as aggregates, how well each candidate signal separates wrong fields from right ones; recommend which (if any) to show.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Arithmetic (items, subtotal, tax vs total) | Free | Measured: flags 5 of 49, catches 2 of 9 wrong totals | test |
| Day/month could be swapped | Free | Measured: flagged dates are wrong less often than the rest; dropped | ✗ |
| Token probabilities from the model (Ollama `logprobs`, works on 0.40.12 with the JSON schema) | The model's own doubt, per digit | One more number per field to calibrate | test |
| Ask for the cash tendered and change, check total = tendered − change | Targets the main total error (5 of 9 too high) | Longer answers | later, if needed |

## Consequences

**Positive:** the review can point at the fields most likely wrong.

**Negative / Trade-offs accepted:** none (research).

**Risks / Open questions:** 49 receipts is a small sample; thresholds may overfit.

## Definition of done

- [ ] Each signal's flag rate and how many wrong fields it catches, on the labelled receipts
- [ ] Recommendation: which signal, which threshold, or none

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 building — owner: "proceed with next item you suggested" (expense-api IDEA-0012). Cheap signals on the 49 labelled reads of the WORK-0014 run: arithmetic flagged 5, 2 wrong (catches 2 of 9 wrong totals; unflagged 7 of 44 wrong); day/month ambiguity flagged 12, 3 wrong (unflagged 14 of 37 wrong): not useful. Wrong dates are mostly misread digits (month 5, day 2, year 2, missing 3, swapped 1, other 2); wrong totals 5 too high, 4 too low. Ollama 0.40.12 returns per-token `logprobs` with the JSON-schema format (checked on the public sample).

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
