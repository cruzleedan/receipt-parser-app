---
id: 0034
title: "Report actual backend instead of mislabelling vision runs as Gemini"
status: shipped
kind: fix
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0034 — Report actual backend instead of mislabelling vision runs as Gemini

## Problem

While preparing the WORK-0032 experiments, `bench/run_bench.py:run_parser` was found to label any response with zero OCR time as `gemini`. The production VLM also reports zero OCR time, so benchmark records can falsely imply cloud processing. The API metadata had no explicit field to distinguish these paths. OCR timing is not a backend identifier.

## Decision

Add optional `backend` and `model` fields to processing metadata and fill them at the pipeline that actually answered, including fallback. Use the explicit identifier in benchmark recording and live integration assertions. For historical API responses without the identifier, report `vision_unknown` rather than guessing Gemini. Do not rewrite historical benchmark files.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Address the owning configuration/metadata boundary | Explicit behavior; directly testable | Small implementation change | Yes |
| Keep the current behavior | No changes | Retains the confirmed issue | No |

## Consequences

**Positive:** accurate backend provenance and stronger regression checks; additive response fields preserve existing callers.

**Trade-offs:** consumers that want provenance should read the new fields instead of inferring from timings.

## Definition of done

- [x] Every successful production backend sets its actual identifier and configured model.
- [x] The benchmark never labels an unidentified zero-OCR response as Gemini.
- [x] Unit and real-model integration checks verify VLM identity; fallback responses identify the text pipeline.

## Log

- 2026-11-17 building — additional confirmed review finding discovered during the owner-authorized implementation and experiment preparation.
- 2026-11-17 shipped — owner-authorized fixes and local study completed; 85 unit checks passed, final candidate and production integration checks each 4 passed. Parser image 56d70051e9b6; repository utilities covered by focused regressions; context validation passed.
