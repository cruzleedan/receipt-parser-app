---
id: 0011
title: "Collect confirmed receipt corrections, then fine-tune the parser model"
status: proposed
kind: feature
opened: 2026-11-12
decided: ~
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0011 — Collect confirmed receipt corrections, then fine-tune the parser model

| | |
|---|---|
| **Opened** | 2026-11-12 |
| **Status** | proposed |
| **Kind** | feature |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

On the owner's receipts the best local model gets totals right 76% of the time and dates 55% (WORK-0009). Fine-tuning on receipts like the app's is the main lever left once prompt fixes level off; a published report lifted a 4B Qwen vision model from 0.63 to 0.77 F1 this way (ReceiptBench, cited in WORK-0004, not re-checked).

## Decision

Proposed, in two stages:

1. **Collect.** When a user confirms or corrects parsed fields (web `ParsedReceiptConfirmationModal`, Flutter equivalent), store the model's answer and the confirmed values against the receipt, only for users who opted in. Needs consent wording and retention rules (expense WORK-0038 privacy, WORK-0048 retention) and a Flutter change.
2. **Fine-tune** once there are several hundred confirmed receipts: LoRA on Qwen3.5-4B, or on a 0.8B model (OvisOCR3 base) for speed. Training needs a GPU d3 does not have: a rented GPU means the receipts leave d3 for the run, which needs the owner's decision and the users' consent. Merge, convert to GGUF with the vision projector (to be verified for Qwen3.5), serve in Ollama, and score with `bench/score_labels.py` before switching.

Skip stage 2 if WORK-0010 finds a published receipt-tuned model that is good enough.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Learn from confirmed corrections | Labels come free from normal use | Consent, retention, Flutter work | ✓ (proposed) |
| Label a batch by hand | No app change | Owner time; small set | ✗ |
| Use a published fine-tune | No training | May not fit Philippine receipts | WORK-0010 |

## Consequences

**Positive:** accuracy improves on the receipts the app actually sees.

**Negative / Trade-offs accepted:** new stored data and a consent flow.

**Risks / Open questions:** cloud GPU and data leaving d3; GGUF conversion of a fine-tuned Qwen3.5 vision model unverified.

## Definition of done

- [ ] Consent and retention decided with the owner
- [ ] Corrections captured (API, web, Flutter)
- [ ] Fine-tune trained, served and scored against the owner's labels

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 proposed — owner asked whether the model can be trained over time.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
