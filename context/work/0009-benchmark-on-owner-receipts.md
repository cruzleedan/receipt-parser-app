---
id: 0009
title: "Spike: rerun the WORK-0006 benchmark on the owner's own receipts"
status: shipped
kind: spike
opened: 2026-11-12
decided: 2026-11-12
branch: spike/0009-own-receipts-benchmark
supersedes: ~
superseded-by: ~
---

# WORK-0009 — Spike: rerun the WORK-0006 benchmark on the owner's own receipts

| | |
|---|---|
| **Opened** | 2026-11-12 |
| **Status** | shipped |
| **Kind** | spike |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

WORK-0006 measured on 50 Indonesian CORD receipts, which may be in the models' training data and have no merchant or date labels. The owner supplied about 400 real receipt photos of varied layouts (2026-11-12), mostly theirs and some from friends, possibly with duplicates.

## Decision

- **Handling:** the images are personal data, some of third parties. They stay on d3 in `/home/dan/receipt-bench/` (outside every repository, mode 700), are never committed, and are never sent to Gemini or any other cloud model for parsing. Only aggregate scores go into this item. (Exception, disclosed to the owner 2026-11-12: the agent viewed 18 photos itself while checking duplicate detection, which sent them to Anthropic's API; it stopped viewing photos after that.) They are deleted when this item ships unless the owner asks to keep them.
- **Duplicates:** removed by file hash, then by perceptual hash.
- **Runs:** Qwen3.5-4B, Gemma 4 E4B, GLM-OCR, OvisOCR3 and the current local pipeline, locally on the 890M (as WORK-0006).
- **Scores without labels:** valid JSON, time per receipt, arithmetic consistency (items vs subtotal, subtotal + tax vs total), agreement between models on total, date and merchant.
- **Scores with labels:** the owner confirms total, date and merchant on a sample (about 60) in a local labelling page pre-filled from the models.

## Results (2026-11-12)

465 photos after unpacking (2 videos skipped, no byte-identical copies). A perceptual-hash duplicate pass was dropped: it matched different receipts (8 of 8 sampled pairs). Every third photo (155) was run through each candidate, locally on the 890M (Vulkan), with every schema field required (an earlier optional-field schema let models skip merchant, date and subtotal; restarted). No cloud backend was run.

Without labels (155 receipts; agreement = same answer as the majority of the five runs):

| Candidate | Valid JSON | Items add up | Agrees: total | Agrees: date | Agrees: merchant | Median s | p90 s |
|---|---|---|---|---|---|---|---|
| **Qwen3.5-4B** | 99% | 66% | 89% | 85% | 92% | 14.1 | 38.3 |
| Gemma 4 E4B | 99% | 65% | 77% | 77% | 86% | 6.7 | 16.4 |
| GLM-OCR | 99% | 61% | 38% | 91% | 92% | 4.8 | 6.1 |
| OvisOCR3 | 99% | 40% | 77% | 73% | 86% | 3.3 | 7.8 |
| Current local pipeline | 75% | 19% | 66% | 67% | 54% | 15.2 | 70.0 |

The current pipeline failed 39 of 155 (19 hit the 70 s deadline, 20 answered 422).

Against the owner's labels (60 random receipts from the 155; 2 marked unreadable, 58 scored; `bench/score_labels.py`):

| Candidate | Total | Date | Merchant | All three | No answer |
|---|---|---|---|---|---|
| **Qwen3.5-4B** | **76%** (44) | **55%** (32) | **88%** (51) | **36%** (21) | 0 |
| Gemma 4 E4B | 52% (30) | 40% (23) | 84% (49) | 14% (8) | 0 |
| GLM-OCR | 28% (16) | 55% (32) | 86% (50) | 16% (9) | 1 |
| OvisOCR3 | 48% (28) | 43% (25) | 72% (42) | 22% (13) | 1 |
| Current local pipeline | 40% (23) | 36% (21) | 52% (30) | 12% (7) | 16 |

Reading the results:
- Qwen3.5-4B is best on every field, as on CORD, but real receipts are harder: 76% totals vs 91% on CORD.
- Dates are the weakest field for every model. Of Qwen's 26 date errors, 5 are month/day swaps and 3 read a two-digit year as the day (MM/DD/YY receipts); the rest are other misreadings. Asking for the date as printed and converting it in code (MM/DD first) should recover some.
- Gemma's wrong totals are often the subtotal (7 of 28); Qwen's are mostly other misreadings (13 of 14).
- Even the best model gets all three fields right on about a third of receipts, so the app's confirm-before-saving step (`ParsedReceiptConfirmationModal`) must stay.
- Limits: 58 labels from one owner; some labels may be off (two flagged to the owner).

## Recommendation

Unchanged: Qwen3.5-4B as the local primary backend (WORK-0008), with the date taken as printed and normalised in code, and the confirmation step kept. Re-score with `bench/score_labels.py` after the prompt change.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Consistency and agreement, plus a small owner-labelled sample | Real accuracy on real receipts for 15–20 minutes of owner time | Sample is small | ✓ |
| Use one model's answer as truth | No owner time | Measures agreement with that model, not accuracy | ✗ |
| Gemini as the reference | Strong model | Sends friends' receipts to Google; 20 requests a day | ✗ |

## Consequences

**Positive:** the WORK-0008 choice rests on receipts like the app's.

**Negative / Trade-offs accepted:** about 20 minutes of owner labelling.

**Risks / Open questions:** HEIC or PDF files need conversion.

## Definition of done

- [x] Duplicates removed; counts recorded
- [x] All candidates run; unlabelled scores recorded
- [x] Owner-labelled sample scored
- [x] Recommendation for WORK-0008 confirmed or changed
- [x] Images deleted from d3 (or kept on the owner's request)

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 building — owner offered about 400 receipt photos for a rerun; some are friends'.
- 2026-11-12 run — 465 photos unpacked; 155 run through five local candidates; owner labelled 60 (2 unreadable). Results above. The agent viewed 18 photos while debugging duplicate detection, which sent them to Anthropic's API; disclosed to the owner and stopped.
- 2026-11-12 shipped — owner asked to keep the photos, model answers and labels in `/home/dan/receipt-bench/` (mode 700) for re-scoring WORK-0008; delete them when WORK-0008 ships unless the owner says otherwise.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
