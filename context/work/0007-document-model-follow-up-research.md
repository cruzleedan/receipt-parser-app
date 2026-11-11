---
id: 0007
title: "Spike: OvisOCR2, Docling, Donut and GLM-OCR for receipts"
status: shipped
kind: spike
opened: 2026-11-11
decided: 2026-11-11
branch: spike/0006-0007-benchmark
supersedes: ~
superseded-by: ~
---

# WORK-0007 — Spike: OvisOCR2, Docling, Donut and GLM-OCR for receipts

| | |
|---|---|
| **Opened** | 2026-11-11 |
| **Status** | shipped |
| **Kind** | spike |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

WORK-0004 covered general vision-language models well but skipped or barely covered the document-specialist models the owner named (2026-11-11): OvisOCR2 (not covered), IBM Docling / Granite-Docling and Donut CORD-v2 fine-tunes (skipped as older or weaker without checking), GLM-OCR (covered without receipt evidence).

## Decision

Research only: for each, what it is, size, licence, how it runs on d3 (Ollama, llama.cpp, Transformers on CPU), what it outputs (text, layout, or receipt fields), and any receipt evidence (CORD, SROIE, ReceiptBench). Feed the runnable ones into the WORK-0006 benchmark.

## Options considered

Research of 2026-11-11 (sub-agent; model cards and papers below; scores are vendor figures unless noted).

| Model | What it is | Output | Receipt evidence | Runs here | Licence | Verdict |
|---|---|---|---|---|---|---|
| OvisOCR2 (ATH-MaaS, Jul 2026) | 0.8B, from Qwen3.5-0.8B | Page Markdown only | none | GGUF / Transformers | Apache-2.0 | skip: no field extraction; superseded by OvisOCR3 |
| **OvisOCR3** (ATH-MaaS, Oct 2026) | 0.8B, same base | Markdown, plus three key-field modes to JSON (open key-value, field list, schema template; prompted, not enforced) | OCRBench KIE 90.5, CC-OCR KIE 88.7; no CORD/SROIE | community GGUF `hf.co/mradermacher/OvisOCR3-GGUF` (Q4_K_M 529 MB, mmproj) | Apache-2.0 | **benchmark** |
| Granite-Docling-258M (IBM, Sep 2025) | 258M, Idefics3 | DocTags layout → Markdown/JSON; no key fields | none | Ollama `ibm/granite-docling:258m` | Apache-2.0 | skip: layout, not receipt fields; a VLM extracting fields directly makes a layout front-end unnecessary |
| Donut CORD-v2 (Clova, 2022) | ~0.2B, OCR-free | CORD schema tokens → JSON | CORD TED accuracy 91.3 (in-distribution); trained on 800 Indonesian receipts; no merchant/date fields | Transformers on CPU | MIT | **benchmark as a CORD baseline only** (says nothing about other layouts) |
| **GLM-OCR** (zai-org, Mar 2026) | ~0.9B | Text/table/figure; JSON-template extraction prompt | no numbers published | Ollama `glm-ocr:q8_0` (1.8 GB) | MIT | **benchmark** |
| NuExtract 2.0 (2B) | Template → JSON extractor | JSON | none checked | unverified | unverified | optional |

Benchmark set for WORK-0006: CORD-v2 test split (`naver-clova-ix/cord-v2`, 100 receipts, CC-BY-4.0). It has no merchant or date ground truth, uses Indonesian number formatting, and may be in some models' training data.

Sources: huggingface.co/ATH-MaaS/OvisOCR2, huggingface.co/ATH-MaaS/OvisOCR3, huggingface.co/mradermacher/OvisOCR3-GGUF, huggingface.co/ibm-granite/granite-docling-258M, ollama.com/ibm/granite-docling, docling-project.github.io/docling/examples/extraction, huggingface.co/naver-clova-ix/donut-base-finetuned-cord-v2, github.com/clovaai/donut, huggingface.co/zai-org/GLM-OCR, ollama.com/library/glm-ocr, arxiv.org/html/2603.10910, huggingface.co/datasets/naver-clova-ix/cord-v2.

## Consequences

**Positive:** WORK-0006 tests the candidates the owner expects, not only general VLMs.

**Negative / Trade-offs accepted:** none; research only.

**Risks / Open questions:** OvisOCR2 may be new or thinly documented.

## Definition of done

- [x] Each model described with sources and a verdict for WORK-0006 (benchmark / skip, with reason)

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-11 building — owner asked for the follow-up research and the benchmark ("go ahead with your recommended next steps"); delegated to a research sub-agent.
- 2026-11-11 shipped — OvisOCR3, GLM-OCR and Donut (CORD baseline) go into WORK-0006; OvisOCR2 and Granite-Docling skipped with reasons.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
