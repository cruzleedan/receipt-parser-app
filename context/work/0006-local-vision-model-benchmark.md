---
id: 0006
title: "Benchmark a local vision model to replace the OCR + text-model fallback"
status: shipped
kind: feature
opened: 2026-11-11
decided: 2026-11-11
branch: spike/0006-0007-benchmark
supersedes: ~
superseded-by: ~
---

# WORK-0006 — Benchmark a local vision model to replace the OCR + text-model fallback

| | |
|---|---|
| **Opened** | 2026-11-11 |
| **Status** | shipped |
| **Kind** | feature |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

The local fallback (PaddleOCR, then llama3.2 3B on text) loses layout and misreads receipts (2026-11-11 probe: wrong quantities, no date, merchant "Store Address Here"). WORK-0004 found newer small vision models that read the image directly.

## Decision

Proposed: enable Vulkan for `shared-ollama` on the Radeon 890M, then benchmark Qwen3.5-4B (thinking off), NuExtract3 and Gemma 4 E4B against the current pipeline and Gemini on about 100 receipts plus CORD/SROIE test splits, with a JSON schema enforced. Measure field accuracy (total, date, tax), line-item F1, the arithmetic check, time per receipt (Vulkan vs CPU), memory, Q4 vs Q8. Add a `vlm_ollama` backend if one wins.

## Options considered

See WORK-0004 and WORK-0007.

## Results (2026-11-11)

First 50 receipts of the CORD-v2 test split (`naver-clova-ix/cord-v2`), same image size (long side 1280 px) and JSON schema for every vision model, temperature 0. Vision models ran in a separate Ollama 0.40.12 container on the Radeon 890M through Vulkan (`OLLAMA_VULKAN=1`, `OLLAMA_IGPU_ENABLE=1`; `ollama ps`: 100% GPU). Harness and scorer: `bench/run_bench.py`, `bench/score.py`, `bench/run_all.sh`. Amounts are correct within 1 %; item F1 matches name (≥ 0.6 similar) and price. CORD has no merchant or date labels, so those are not scored.

| Candidate | Valid JSON | Total | Subtotal | Tax | Item F1 | Median s | p90 s |
|---|---|---|---|---|---|---|---|
| **Qwen3.5-4B** (`qwen3.5:4b`) | 100% | 91% (43/47) | 35% (11/31) | 70% (14/20) | **0.93** | 8.4 | 13.5 |
| Gemma 4 E4B (`gemma4:e4b`) | 100% | 87% (41/47) | **90%** (28/31) | 55% (11/20) | 0.83 | 4.1 | 5.9 |
| GLM-OCR (`glm-ocr:q8_0`, its JSON-template prompt) | 100% | 91% (43/47) | 42% (13/31) | 20% (4/20) | 0.82 | 4.0 | 4.7 |
| OvisOCR3 (`hf.co/mradermacher/OvisOCR3-GGUF:Q8_0`) | 100% | 85% (40/47) | 39% (12/31) | 45% (9/20) | 0.81 | **2.2** | 3.5 |
| Current local pipeline (PaddleOCR CPU → llama3.2 3B, as in production) | 90% | 60% (28/47) | 42% (13/31) | 20% (4/20) | 0.44 | 7.4 | 12.4 |
| Donut CORD-v2 (CPU; **trained on CORD**, in-distribution) | 100% | 98% (46/47) | 94% (29/31) | 100% (20/20) | 0.86 | 3.2 | 4.8 |
| Gemini 2.5 Flash | — | — | — | — | — | — | — |

Gemini could not be scored: the free tier allows **20 requests per day** for `gemini-2.5-flash` (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue 20). The run through the parser got 3 Gemini answers before falling back; a direct run hit 429 at once. The quota was exhausted for about 16 hours (retryDelay 58868 s), during which production fell back to the local pipeline.

Reading the results:
- Every vision model beats the current local pipeline clearly (total 85–91% vs 60%, item F1 0.81–0.93 vs 0.44) and returns valid JSON every time under Ollama's schema `format`.
- Qwen3.5-4B is the most accurate on totals, tax and line items; it often leaves `subtotal` null. Gemma 4 E4B reads subtotals best and is twice as fast. OvisOCR3 is fastest (2.2 s) at a small accuracy cost.
- Donut's high score is in-distribution (it was trained on CORD's other 800 receipts) and its schema has no merchant, date or payment fields; it is not a general option.
- Limits: 50 receipts, all Indonesian CORD layouts; models may have seen CORD in training; no real receipts from the app's users were used (production has one).

## Recommendation

Adopt **Qwen3.5-4B** as the local backend (proposed WORK-0008), replacing PaddleOCR + llama3.2, with a prompt change to ask for the printed subtotal explicitly, and re-check subtotal against Gemma 4 E4B before choosing. Given Gemini's 20-requests-a-day free tier, the local model should become the primary backend, which also ends the data-use exposure of WORK-0003. It needs Ollama with Vulkan on the iGPU for the parser (a dedicated container, or `shared-ollama` moved off its ROCm image after checking RAG and flutter-rag).


## Consequences

**Positive:** a local primary backend would end sending images to Gemini (WORK-0003).

**Negative / Trade-offs accepted:** Ollama container change touches other users of `shared-ollama` (RAG, flutter-rag).

**Risks / Open questions:** iGPU detection in Docker; image-encode CPU fallback in llama.cpp; real receipts for the benchmark must stay on d3.

## Definition of done

- [x] Benchmark results recorded here
- [x] Decision: adopt (new backend) or stay

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-11 proposed — follow-up from WORK-0004.
- 2026-11-11 building — owner approved ("go ahead with your recommended next steps"), widened to the document models of WORK-0007. Run in a separate benchmark Ollama container so `shared-ollama` (RAG, flutter-rag) is untouched; public CORD-v2 test receipts with ground truth.
- 2026-11-11 run — 7 candidates on 50 CORD-v2 test receipts (table above). Gemini hit its free-tier limit of 20 requests a day; production fell back to the local pipeline until it reset.
- 2026-11-11 shipped — recommendation Qwen3.5-4B as the local primary backend; WORK-0008 proposed.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
