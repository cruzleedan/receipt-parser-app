---
id: 0006
title: "Benchmark a local vision model to replace the OCR + text-model fallback"
status: proposed
kind: feature
opened: 2026-11-11
decided: ~
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0006 — Benchmark a local vision model to replace the OCR + text-model fallback

| | |
|---|---|
| **Opened** | 2026-11-11 |
| **Status** | proposed |
| **Kind** | feature |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

The local fallback (PaddleOCR, then llama3.2 3B on text) loses layout and misreads receipts (2026-11-11 probe: wrong quantities, no date, merchant "Store Address Here"). WORK-0004 found newer small vision models that read the image directly.

## Decision

Proposed: enable Vulkan for `shared-ollama` on the Radeon 890M, then benchmark Qwen3.5-4B (thinking off), NuExtract3 and Gemma 4 E4B against the current pipeline and Gemini on about 100 receipts plus CORD/SROIE test splits, with a JSON schema enforced. Measure field accuracy (total, date, tax), line-item F1, the arithmetic check, time per receipt (Vulkan vs CPU), memory, Q4 vs Q8. Add a `vlm_ollama` backend if one wins.

## Options considered

See WORK-0004.

## Consequences

**Positive:** a local primary backend would end sending images to Gemini (WORK-0003).

**Negative / Trade-offs accepted:** Ollama container change touches other users of `shared-ollama` (RAG, flutter-rag).

**Risks / Open questions:** iGPU detection in Docker; image-encode CPU fallback in llama.cpp; real receipts for the benchmark must stay on d3.

## Definition of done

- [ ] Benchmark results recorded here
- [ ] Decision: adopt (new backend) or stay

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-11 proposed — follow-up from WORK-0004.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
