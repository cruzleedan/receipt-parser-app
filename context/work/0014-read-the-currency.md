---
id: 0014
title: "Read the currency from receipts"
status: proposed
kind: feature
opened: 2026-11-12
decided: ~
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0014 — Read the currency from receipts

| | |
|---|---|
| **Opened** | 2026-11-12 |
| **Status** | proposed |
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

- [ ] Field in prompt, schema and response; scored on the labelled receipts; expense-api and web use it

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 proposed — found while checking expense-tracker WORK-0034 (a peso receipt defaulted to USD).

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
