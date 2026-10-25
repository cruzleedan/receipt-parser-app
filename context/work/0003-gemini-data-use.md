---
id: 0003
title: "Receipt images and Gemini: free tier now, paid tier next"
status: accepted
kind: infra
opened: 2026-10-25
decided: 2026-10-25
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0003 — Receipt images and Gemini: free tier now, paid tier next

| | |
|---|---|
| **Opened** | 2026-10-25 |
| **Status** | accepted |
| **Kind** | infra |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Production runs with `PARSER_BACKEND=gemini` and model `gemini-2.5-flash`: the receipt image itself is sent to Google's Gemini API. The owner confirmed (2026-10-25) the key is on Google's **free tier**, whose terms allow Google to use submitted content to improve its products; the paid tier does not. Users of the Expense app must be told, and the owner plans to move to paid.

## Decision

1. Now: the Expense privacy policy (expense WORK-0038) and expense-api's retention policy (WORK-0048) state that receipt images sent for auto-fill are processed by Google's Gemini API on a tier where Google may use them to improve its products; auto-fill is optional.
2. When the owner subscribes: move the key to a billing-enabled project, record the date here, and update both policies to the paid-tier wording.
3. Until then, keep the local fallback (PaddleOCR + Ollama) working, so auto-fill can be switched to local only (`PARSER_BACKEND=ollama`) if the owner prefers before paying.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Disclose now, move to paid later | Truthful today; no service change | Free-tier data use in the meantime | ✓ |
| Switch to the local pipeline until paid | No third party | Lower accuracy and slower | ✗ (available as a switch) |

## Consequences

**Positive:** users know where their receipt images go.

**Negative / Trade-offs accepted:** free-tier terms until the subscription.

**Risks / Open questions:** the date of the subscription.

## Definition of done

- [ ] Both policies disclose the free tier
- [ ] Key moved to a paid project; policies updated
- [ ] Log records the date

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-10-25 accepted — owner: free Gemini key now, paid models soon.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
