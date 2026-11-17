---
id: 0033
title: "Persist OCR model cache across parser recreation"
status: shipped
kind: infra
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0033 — Persist OCR model cache across parser recreation

## Problem

Deployment preparation for WORK-0017–0032 found that PaddleOCR downloads its model files into `/root/.paddlex` in the container write layer. Compose did not persist that directory. Recreating the parser therefore loses roughly 93 MB of cached model/configuration files and makes startup depend on downloading them again, even when the application image is already built.

## Decision

Persist `/root/.paddlex` in the Compose `parser-ocr-models` named volume. Seed it with the existing working production cache before recreation. It contains OCR model assets, not receipt images or extraction output. Keep the parser runtime version pinned as before; this cache does not upgrade OCR models.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Address the owning configuration/metadata boundary | Explicit behavior; directly testable | Small implementation change | Yes |
| Keep the current behavior | No changes | Retains the confirmed issue | No |

## Consequences

**Positive:** rebuilds reuse the same working models and avoid a startup network/download dependency.

**Trade-offs:** roughly 93 MB persistent disk space; future deliberate model upgrades must manage the cache explicitly. New installations still need an initial model download.

## Definition of done

- [x] Existing production OCR cache copied into the named volume without removing any existing files.
- [x] Parser recreated with the volume, model-cache reuse observed, and readiness/integration checks pass.
- [x] Cache behavior documented; no receipt data added to the cache.

## Log

- 2026-11-17 building — discovered during the owner-authorized fixes/deployment preparation; added a persistent model cache to prevent avoidable cold-start downloads.
- 2026-11-17 shipped — owner-authorized fixes and local study completed; 85 unit checks passed, final candidate and production integration checks each 4 passed. Parser image 56d70051e9b6; repository utilities covered by focused regressions; context validation passed.
