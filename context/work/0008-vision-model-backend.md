---
id: 0008
title: "Local vision-model backend (Qwen3.5-4B) as the primary parser"
status: building
kind: feature
opened: 2026-11-11
decided: 2026-11-12
branch: feat/0008-vision-model-backend
supersedes: ~
superseded-by: ~
---

# WORK-0008 — Local vision-model backend (Qwen3.5-4B) as the primary parser

| | |
|---|---|
| **Opened** | 2026-11-11 |
| **Status** | building |
| **Kind** | feature |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

WORK-0006 measured the current local fallback at 60% correct totals and 0.44 item F1 on CORD; Qwen3.5-4B reached 91% and 0.93 in 8.4 s median on the iGPU. The primary backend, Gemini's free tier, allows only 20 requests a day and may use the images (WORK-0003).

## Decision

Proposed: add a `vlm_ollama` backend (one image call, JSON schema through Ollama `format`, temperature 0, thinking off) and make it the default; keep PaddleOCR + llama3.2 only if a fallback is still wanted. Run it on an Ollama with Vulkan on the 890M: a dedicated `parser-ollama` container (simplest, no effect on other services) or `shared-ollama` moved to the Vulkan image after checking RAG and flutter-rag. Ask explicitly for the printed subtotal and re-compare Qwen3.5-4B with Gemma 4 E4B on subtotal before fixing the model. Fits WORK-0005's 70 s deadline (p90 13.5 s on CORD, 38.3 s on the owner's receipts). WORK-0009 confirmed the choice on the owner's receipts (totals 76%, merchant 88%, date 55%): ask for the date exactly as printed and normalise it in code (MM/DD first), and keep the app's confirmation step.

## Options considered

See WORK-0006.

## Consequences

**Positive:** better accuracy than either current path; no images leave d3; no daily cap.

**Negative / Trade-offs accepted:** about 4 GB of shared memory while loaded; GPU contention with other Ollama users if shared.

**Risks / Open questions:** measured on 58 owner-labelled receipts only (WORK-0009); the Expense privacy text (expense WORK-0038) changes once Gemini is gone.

## Definition of done

- [x] Backend, tests and deployment; benchmark rerun through the parser
- [ ] Privacy and retention wording updated if Gemini is removed

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-11 proposed — from WORK-0006's results.
- 2026-11-12 updated — WORK-0009 (owner's receipts) confirms Qwen3.5-4B; adds the date-normalisation step.
- 2026-11-12 building — owner: "proceed with your recommendations" (cheap prompt fixes scored against the WORK-0009 labels, then the backend).
- 2026-11-12 prompt results (owner's 58 labels; total / date / merchant / all three): baseline prompt 76/55/88/36%; date-as-printed + total rule 86/60/93/50%; the same without the example date (the model had copied it into an answer) 84/71/91/57%. NuExtract3 (WORK-0010) 81/47/91/38% at best: Qwen3.5-4B kept. Bench date scoring now uses the parser's own `src/dates.py`.
- 2026-11-12 implemented and verified — `vlm_ollama` backend (`src/vlm_service.py`, `src/dates.py`), month-first date normalisation, answer cleaning (no total → fallback; fractional quantities → 1), `parser-ollama` container (Ollama 0.40.12, Vulkan on the 890M) in `compose.yml`. `pytest`: 28 passed. End to end through the parser on the labelled receipts: 84/64/90/48%, 59 of 60 answered by the vision model (1 fell back: no total), median 16.1 s, p90 38.9 s, max 54.9 s, inside the 70 s deadline.
- 2026-11-12 deploy regression — `VLM_KEEP_ALIVE=-1` reached Ollama as the string "-1" (400 "missing unit in duration"), so every production parse fell back to the local pipeline (still 200). Tests had stubbed the Ollama call. No rollback image existed (the old image's layers had been cleaned up); fixed forward: numeric values are sent as numbers, with a test.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
