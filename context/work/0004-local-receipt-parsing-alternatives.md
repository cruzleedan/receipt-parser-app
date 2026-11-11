---
id: 0004
title: "Spike: better local alternatives to PaddleOCR + Ollama for receipt parsing"
status: shipped
kind: spike
opened: 2026-11-11
decided: 2026-11-11
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0004 — Spike: better local alternatives to PaddleOCR + Ollama for receipt parsing

| | |
|---|---|
| **Opened** | 2026-11-11 |
| **Status** | shipped |
| **Kind** | spike |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Production parses with Google Gemini (`gemini-2.5-flash`) on the free tier, where Google may use the receipt images to improve its products (WORK-0003). The local fallback is the WORK-0001 two-stage pipeline: PaddleOCR (CPU) for text, then `llama3.2` 3B on Ollama to structure it as JSON. The 3B text model never sees the image, so layout (columns, totals versus subtotals) is lost, and the pipeline was chosen in early 2026. Vision-language and document models have moved quickly since. The owner asked (2026-11-11) for research on better local options for 2026–2027.

Hardware on d3: AMD Ryzen AI 9 HX 370 (12 cores / 24 threads, XDNA 2 NPU), Radeon 890M integrated GPU (RDNA 3.5, shares system memory), 58 GB RAM, no discrete GPU. Ollama runs in the `shared-ollama` container.

## Decision

Research only. Compare local options for receipt image → structured JSON (merchant, date, line items, tax, total): accuracy on receipts, latency on the d3 hardware above, memory, licence, how it runs (Ollama, llama.cpp, vLLM, ONNX/NPU), and maturity. Recommend one option, or none, with a follow-up feature item if a switch is worthwhile. No code changes under this item.

## Options considered

Research of 2026-11-11 (sub-agent, web sources below). Latencies are **estimates** from text-model benchmarks on the HX 370 / 890M (Qwen3-8B Q4 on Vulkan: ~322 tok/s prompt, ~13 tok/s generation; ROCm ~4.8 tok/s); no source timed VLM image encoding on this chip.

| Candidate | Runs here via | Est. per receipt | Receipt evidence | Licence | Chosen? |
|---|---|---|---|---|---|
| Qwen3.5-4B (Mar 2026, multimodal), thinking off, JSON-schema `format` | Ollama `qwen3.5:4b`, Vulkan | ~10–20 s | OCRBench 85.0, OmniDocBench 86.2 (vendor) | Apache-2.0 | ✓ to benchmark first |
| NuExtract3 (4B Qwen3.5 extraction fine-tune, May 2026) | GGUF in Ollama; image input via mmproj unconfirmed | ~10–20 s | Vendor extraction test 0.651 vs Qwen3.5-4B 0.417 | Apache-2.0 | A/B arm |
| Gemma 4 E4B | Ollama `gemma4:e4b` | ~15–25 s | OmniDocBench edit 0.181 (vendor) | Apache-2.0 | runner-up |
| Qwen3-VL-4B/8B (Oct 2025) | Ollama `qwen3-vl` | 15–40 s | ReceiptBench F1 0.626 / 0.655 (Gemini-3-Pro 0.737; fine-tuned 8B 0.795) | Apache-2.0 | ✗ superseded by Qwen3.5 |
| PaddleOCR-VL-1.5 / GLM-OCR (0.9B OCR models) | llama.cpp / Ollama | 1–5 s OCR only | ReceiptBench 0.634 (PaddleOCR-VL), weak on line items | Apache-2.0 / MIT | ✗ OCR only, needs a second model |
| DeepSeek-OCR-2, olmOCR, dots.ocr, MinerU | vLLM / ROCm (shaky on gfx1150) | slow here | ReceiptBench ≤ 0.623 | MIT / Apache | ✗ |
| NPU (FastFlowLM via Lemonade) | XDNA 2 on Linux | unknown | none | proprietary NPU kernels, revenue-capped | ✗ immature |

Runtime: use **Vulkan** in Ollama on the 890M (pass `/dev/dri`; iGPUs may need opting in), not ROCm (gfx1150 only in preview; slower than CPU in reports) nor the NPU. Watch a llama.cpp issue where image encoding falls back to CPU (82 s for a 9B image); cap image pixels.

Sources: Qwen3.5-4B and NuExtract3 model cards (huggingface.co/Qwen/Qwen3.5-4B, huggingface.co/numind/NuExtract3), ollama.com/library/qwen3.5 and /gemma4, ReceiptBench arXiv 2605.22413, msf.github.io/blogpost/local-llm-performance-framework13.html, rocm.docs.amd.com 7.11/7.13 preview notes, docs.ollama.com/gpu, github.com/ggml-org/llama.cpp/issues/22582, huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5-GGUF, github.com/zai-org/GLM-OCR.

Watch for 2027 (unverified): smaller Qwen3.6+ VLMs, ROCm gfx1150 leaving preview, published NPU VLM benchmarks, OCR models with native key-field extraction, ReceiptBench as a leaderboard.

## Recommendation

Replace the two-stage fallback with one vision model that reads the image: **Qwen3.5-4B** in the existing Ollama container on Vulkan, JSON schema enforced, temperature 0, with NuExtract3 as an A/B arm and Gemma 4 E4B as runner-up. Adopt only after a local benchmark (WORK-0006, proposed): field accuracy for total/date/tax, line-item F1, the arithmetic check, per-receipt time on Vulkan vs CPU, Q4 vs Q8. If it holds, it can become the primary backend and end the Gemini free-tier exposure (WORK-0003).

## Consequences

**Positive:** a grounded choice for removing the dependence on Gemini's free tier, or for a better fallback.

**Negative / Trade-offs accepted:** none; research only.

**Risks / Open questions:** benchmarks published by model authors may not reflect receipts or this hardware; any recommendation needs a local benchmark on `receipts/` before adoption.

## Definition of done

- [x] Candidates compared on accuracy, latency on d3, memory, licence, runtime and maturity, with sources
- [x] One recommendation (or "stay") recorded here with reasons
- [x] Follow-up feature item proposed if a switch is recommended

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-11 building — owner asked for the research; delegated to a research sub-agent.
- 2026-11-11 shipped — research recorded; recommendation Qwen3.5-4B on Ollama/Vulkan, to be benchmarked under WORK-0006 (proposed).

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
