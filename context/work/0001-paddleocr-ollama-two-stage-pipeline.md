---
id: 0001
title: "PaddleOCR + Ollama two-stage pipeline, replacing single-stage Qwen2.5-VL"
status: accepted
kind: infra
opened: 2026-06-11
decided: 2026-06-11
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0001 — PaddleOCR + Ollama two-stage pipeline

| | |
|---|---|
| **Opened** | 2026-06-11 |
| **Status** | accepted |
| **Kind** | infra |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

The prior receipt parser used a single-stage Qwen2.5-VL vision-language
model to go directly from image to structured JSON. This was slow (5-10s per
receipt), memory-heavy (12-15GB), and had a large container footprint
(18GB) — all a problem for a homelab server shared with other services.

## Decision

Replaced the single-stage VLM approach with a **two-stage pipeline**:
PaddleOCR (PP-OCRv4) extracts text from the receipt image, then an Ollama
LLM structures that text into JSON matching the existing API schema. Stage
1 targets 0.5-1s, stage 2 targets 1-2s, for a combined 2-3s per receipt.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Two-stage: PaddleOCR → Ollama LLM (this design) | 2-3x faster; ~60% less memory/container size; OCR and LLM concerns are separable and independently swappable | Two moving parts instead of one; OCR errors can propagate into the LLM stage | ✓ |
| Single-stage VLM (Qwen2.5-VL, prior approach) | One model, simpler pipeline | Slow (5-10s), memory-heavy (12-15GB), large container (18GB) | ✗ |
| Cloud vision API only | Potentially higher accuracy | Data leaves the homelab; ongoing cost; no offline capability | ✗ (kept as opt-in fallback backend — see `gemini_service.py` / `PARSER_BACKEND=gemini`) |

## Consequences

**Positive:**
- 2-3x faster processing, ~60% reduction in memory and container size
  (targets; see Definition of done for what was actually verified)
- OCR and LLM stages can be tuned or swapped independently

**Negative / Trade-offs accepted:**
- Two services to keep healthy instead of one (though both run in the same
  container per `docker/Dockerfile`, with Ollama itself running as the
  separate shared `shared-ollama` service)
- OCR misreads can feed bad input into the LLM structuring stage — no
  cross-validation between stages beyond confidence filtering

**Risks / Open questions:**
- The original plan specified `qwen2.5:7b` as the structuring model; the
  shipped `README.md` documents `llama3.2` instead. Unclear from the
  historical record whether this was a deliberate later change or drift —
  flagging rather than silently picking one. Current `AGENTS.md` doesn't
  pin a specific model name, so treat `README.md` as the more current
  source until confirmed otherwise.

## Definition of done

- [x] `src/ocr_service.py` (PaddleOCR wrapper) implemented
- [x] `src/llm_service.py` (Ollama structuring) implemented
- [x] `src/main.py`, `src/models.py`, `src/config.py` implemented
- [x] API compatibility maintained (`/`, `/health`, `/parse`, `/parse-batch`)
- [ ] Performance targets (2-3s, <8GB memory, 90%+ accuracy) — not verified
      against this record; check current benchmarks if this becomes load-bearing

## Log

- 2026-06-11 accepted — migrated from loose
  `receipt-parser-app-implementation-plan.md` to this work item during
  framework consolidation (2026-08-02); plan was already fully implemented
  at migration time, confirmed against `src/` contents

## Implementation Notes

Two backends are supported at runtime via `PARSER_BACKEND` (see
`AGENTS.md` "Parser Backends") — this work item covers the default
`paddleocr_ollama` path. The `gemini` backend (`src/gemini_service.py`) is
a separate, later addition not covered by the original plan this work item
was migrated from.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
