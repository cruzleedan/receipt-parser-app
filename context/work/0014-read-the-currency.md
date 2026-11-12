---
id: 0014
title: "Read the currency from receipts"
status: shipped
kind: feature
opened: 2026-11-12
decided: 2026-11-12
branch: feat/0014-read-currency
supersedes: ~
superseded-by: ~
---

# WORK-0014 — Read the currency from receipts

| | |
|---|---|
| **Opened** | 2026-11-12 |
| **Status** | shipped |
| **Kind** | feature |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

The parser returns no currency, so expense-tracker WORK-0034's review starts from the report's or the last line's currency and asks the person to check it. Receipts print ₱, PHP, $, USD and so on.

## Decision

Proposed: add `currency` (ISO 4217, null when not printed) to the vision prompt and schema; map symbols (₱ → PHP); expense-api stores it in `receipts.extracted_currency` and the review uses it. Score against the owner's labelled receipts (WORK-0009) first.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Ask the model | One more field | Symbol ambiguity ($) | ✓ |
| Infer from the merchant's country | No model change | Weak | ✗ |

## Consequences

**Positive:** one less field to check.

**Negative / Trade-offs accepted:** slightly longer answers.

**Risks / Open questions:** $ alone is ambiguous; fall back to the person's default.

## Definition of done

- [x] Field in prompt, schema and response; scored on the labelled receipts; expense-api and web use it
- [x] Deployed (the parser is shared by production and the demo)

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 proposed — found while checking expense-tracker WORK-0034 (a peso receipt defaulted to USD).
- 2026-11-12 building — owner: "proceed to next work item you recommend".
- 2026-11-12 implemented — the vision prompt and schema ask for `currency` as an ISO 4217 code ("PHP for ₱, P or PHP, USD only for US$ or USD; null when no currency is printed"); `src/currency.py` keeps only known codes, maps unambiguous symbols (₱, a lone P, US$, €, …) and turns a bare $ or ¥ into null. `ReceiptData`/`ReceiptResponse.currency` (null from the OCR fallback). pytest 46 passed, 4 skipped. expense-api stores it in `receipts.extracted_currency`, returns it in the review suggestion and fills an untouched draft's currency (no database change; parser client `transformResponse` now passes it; PostgreSQL test added, 17 suites pass); expense-tracker uses it in the review and drops "check it" when it was read.
- 2026-11-12 scored on the owner's labelled receipts (WORK-0009; 50 ran, the runner's default limit; 49 labelled), same receipts before/after: total 84→82% (one receipt), date 65→65%, merchant 88→88%, all three 47→45%; currency PHP 42, null 8, wrong 0; median 17.8 s (was 16.8), max 57.0 s, all answered by the vision model. Aggregates only; outputs stay in `~/receipt-bench`.
- 2026-11-12 shipped — owner: "deploy it". Parser rebuilt from `79c83e4` (rollback `receipt-parser-app-parser:rollback-pre-0014-202611122335`), `verify-deployment.sh` 4 passed; a live parse of the public sample answered by the vision model in 11.0 s with currency null (none printed). expense-api and expense-tracker to the demo (live draft check passed, its line and receipt deleted by exact id) and production (backup `~/expense-backups/2026-11-12-1538`, dump 201269 bytes; rollback tags `rollback-pre-0014-202611122337`; healthy; `verify:deployment` OK; parser daily check exit 0).
- 2026-11-12 incident during the deploy (not caused by it) — at 15:38 UTC cloudflared lost all four tunnel connections ("no recent network activity", after DNS failures earlier that night) and stopped retrying; every public hostname answered 530 until the owner restarted it (no sudo for the agent). After the restart all hostnames returned 200.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
