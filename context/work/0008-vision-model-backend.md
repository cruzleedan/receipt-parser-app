---
id: 0008
title: "Local vision-model backend (Qwen3.5-4B) as the primary parser"
status: proposed
kind: feature
opened: 2026-11-11
decided: ~
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0008 — Local vision-model backend (Qwen3.5-4B) as the primary parser

| | |
|---|---|
| **Opened** | 2026-11-11 |
| **Status** | proposed |
| **Kind** | feature |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

WORK-0006 measured the current local fallback at 60% correct totals and 0.44 item F1 on CORD; Qwen3.5-4B reached 91% and 0.93 in 8.4 s median on the iGPU. The primary backend, Gemini's free tier, allows only 20 requests a day and may use the images (WORK-0003).

## Decision

Proposed: add a `vlm_ollama` backend (one image call, JSON schema through Ollama `format`, temperature 0, thinking off) and make it the default; keep PaddleOCR + llama3.2 only if a fallback is still wanted. Run it on an Ollama with Vulkan on the 890M: a dedicated `parser-ollama` container (simplest, no effect on other services) or `shared-ollama` moved to the Vulkan image after checking RAG and flutter-rag. Ask explicitly for the printed subtotal and re-compare Qwen3.5-4B with Gemma 4 E4B on subtotal before fixing the model. Fits WORK-0005's 70 s deadline (p90 13.5 s).

## Options considered

See WORK-0006.

## Consequences

**Positive:** better accuracy than either current path; no images leave d3; no daily cap.

**Negative / Trade-offs accepted:** about 4 GB of shared memory while loaded; GPU contention with other Ollama users if shared.

**Risks / Open questions:** accuracy on the app's own (non-Indonesian) receipts is unmeasured; the Expense privacy text (expense WORK-0038) changes once Gemini is gone.

## Definition of done

- [ ] Backend, tests and deployment; benchmark rerun through the parser
- [ ] Privacy and retention wording updated if Gemini is removed

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-11 proposed — from WORK-0006's results.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
