---
id: 0010
title: "Spike: existing receipt-tuned Qwen (or similar) models we could use as is"
status: shipped
kind: spike
opened: 2026-11-12
decided: 2026-11-12
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0010 — Spike: existing receipt-tuned Qwen (or similar) models we could use as is

| | |
|---|---|
| **Opened** | 2026-11-12 |
| **Status** | shipped |
| **Kind** | spike |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Fine-tuning Qwen3.5-4B on our own receipts (WORK-0011) needs hundreds of labelled receipts, user consent and a rented GPU. Someone may already have published a Qwen (or comparable small vision model) fine-tuned for receipt or invoice extraction that runs on d3.

## Decision

Research only: published fine-tunes of Qwen3.5 / Qwen3-VL / Qwen2.5-VL (and comparable small VLMs) for receipts, invoices or key-field extraction; their base, size, training data, licence, GGUF/Ollama availability and any receipt scores. Candidates that run on d3 go into the WORK-0009 harness against the owner's 58 labels.

## Options considered

Research 2026-11-12 (sub-agent; Hugging Face API and model cards). Most community receipt fine-tunes are trained on CORD only, which has no merchant or date labels.

| Model | Base | Licence | Runs in Ollama | Verdict |
|---|---|---|---|---|
| **numind/NuExtract3** | Qwen3.5-4B, extraction fine-tune (training data undisclosed) | Apache-2.0 | official `numind/nuextract3` (vision) | **benchmarked** |
| ii42/LedgerLens-Qwen2-VL-2B-Receipts | Qwen2-VL-2B (CORD + SROIE) | PolyForm Noncommercial | GGUF + mmproj | skip: licence |
| NuExtract 2.0 (2B/4B/8B) | Qwen2(.5)-VL | 4B non-commercial; 2B/8B MIT | GGUF | skip: superseded by NuExtract3 |
| ratlinghitman/qwen3vl-4b-receipt-extraction, mazenDDr/receipt-vlm-qwen2.5-vl-3b | Qwen3-VL-4B / Qwen2.5-VL-3B (CORD only) | Apache (3B base research-licence) | GGUF | skip: no merchant/date training |
| AlioLeuchtmann/receipt-to-json-models | Qwen3.5-0.8B/2B (~3,800 receipts) | Apache-2.0 | no usable vision GGUF | skip; a useful recipe for WORK-0011 |
| Nanonets-OCR2-3B | Qwen2.5-VL-3B | unclear | community GGUF | skip: OCR to markdown only |

ReceiptBench released a dataset (`T0rl/ReceiptBench`, ~10k receipts, MIT) but no weights.

Result on the owner's 58 labels (total / date / merchant / all three): NuExtract3 with its template 71/47/90/29%, with instructions 81/47/91/38%; Qwen3.5-4B with the WORK-0008 prompt 84/71/91/57%. Nothing published beats the tuned prompt; fine-tuning stays with WORK-0011.

## Consequences

**Positive:** may get most of a fine-tune's gain without training.

**Negative / Trade-offs accepted:** none; research only.

**Risks / Open questions:** community fine-tunes vary in quality and licence.

## Definition of done

- [x] Candidates listed with sources and a verdict (benchmark / skip)
- [x] Runnable candidates scored against the owner's labels

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 building — owner asked a sub-agent to look for existing receipt-tuned models.
- 2026-11-12 shipped — NuExtract3 benchmarked and beaten by Qwen3.5-4B with the WORK-0008 prompt; nothing else usable as is.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
