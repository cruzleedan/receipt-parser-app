---
id: 0015
title: "Spike: which read fields to flag for a second look"
status: shipped
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
| **Status** | shipped |
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

- [x] Each signal's flag rate and how many wrong fields it catches, on the labelled receipts
- [x] Recommendation: which signal, which threshold, or none

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 building — owner: "proceed with next item you suggested" (expense-api IDEA-0012). Cheap signals on the 49 labelled reads of the WORK-0014 run: arithmetic flagged 5, 2 wrong (catches 2 of 9 wrong totals; unflagged 7 of 44 wrong); day/month ambiguity flagged 12, 3 wrong (unflagged 14 of 37 wrong): not useful. Wrong dates are mostly misread digits (month 5, day 2, year 2, missing 3, swapped 1, other 2); wrong totals 5 too high, 4 too low. Ollama 0.40.12 returns per-token `logprobs` with the JSON-schema format (checked on the public sample).
- 2026-11-13 results — the production prompt and schema with `logprobs` on the bench Ollama over the 60 labelled images (58 labelled readable; outputs kept in `~/receipt-bench/runs-0015`). Signal: the lowest probability of any digit token inside the field's value. Total (9 wrong): < 0.5 flags 5 (4 wrong, catches 4/9); < 0.7 flags 11 (8 wrong, catches 8/9; 1 wrong among 47 not flagged); < 0.9 flags 18 (8 wrong); < 0.95 flags 20 (catches 9/9). Date (21 wrong): < 0.5 flags 8 (8 wrong); < 0.7 flags 13 (11 wrong, catches 11/21); < 0.8 flags 18 (12 wrong, catches 12/21); < 0.9 flags 27 (15 wrong). Cost: none measurable (model call median 16.2 s, max 58.8 s, against 17.8/57.0 end to end without).
- 2026-11-13 recommendation — use token probabilities, not arithmetic or date-shape checks. Parser returns the lowest digit probability per field; the API marks the total below 0.7 and the date below 0.8 as "check"; the review highlights them and "Confirm all ready" skips them. Thresholds from 58 receipts: keep them in configuration and re-measure as labels grow. The cash-tendered check is not needed for now (the probability already catches 8 of 9 wrong totals).

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
