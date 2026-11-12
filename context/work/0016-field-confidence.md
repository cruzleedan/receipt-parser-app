---
id: 0016
title: "Report how sure the model was of the total and date"
status: shipped
kind: feature
opened: 2026-11-13
decided: 2026-11-13
branch: feat/0016-field-confidence
supersedes: ~
superseded-by: ~
---

# WORK-0016 — Report how sure the model was of the total and date

| | |
|---|---|
| **Opened** | 2026-11-13 |
| **Status** | shipped |
| **Kind** | feature |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Spike WORK-0015 found that the lowest digit probability in a field separates wrong totals and dates from right ones; expense-api WORK-0083 needs it in the parse response.

## Decision

The vision-model call asks Ollama for `logprobs`; `field_confidence(tokens)` returns `{date, total}` as the lowest probability of any digit token inside each value (null when a field has none). `field_confidence` is in the response; null from the OCR fallback.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Lowest digit probability per field | Measured in WORK-0015 | — | ✓ |
| Mean probability | Smoother | Hides the one doubtful digit | ✗ |

## Consequences

**Positive:** the app can point at doubtful fields.

**Negative / Trade-offs accepted:** a larger Ollama answer (no measurable time cost in WORK-0015).

**Risks / Open questions:** a different model or runtime changes the scale; re-measure on a model change.

## Definition of done

- [x] `field_confidence` in the response; tests
- [x] Deployed; live parse shows it

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-13 building — from spike WORK-0015; owner: "proceed with next item you suggested".
- 2026-11-13 implemented — `logprobs: true` with the JSON schema; `_chat` returns the tokens with the content; `field_confidence` in `ReceiptData`/`ReceiptResponse`. pytest 48 passed, 4 skipped (new: the least sure digit per field, ignoring punctuation; the parse response carries it and the request asks for logprobs).
- 2026-11-13 shipped — owner: "deploy it". Parser rebuilt from `7106bfa` (rollback `receipt-parser-app-parser:rollback-pre-0016-202611130019`); `verify-deployment.sh` 4 passed; live parse of the public sample by the vision model in 11.5 s with field_confidence date 0.997, total 0.994.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
