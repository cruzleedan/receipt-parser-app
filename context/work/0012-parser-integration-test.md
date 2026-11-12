---
id: 0012
title: "Integration test and deployment check against a real parser and model"
status: shipped
kind: infra
opened: 2026-11-12
decided: 2026-11-12
branch: infra/0012-parser-integration-test
supersedes: ~
superseded-by: ~
---

# WORK-0012 — Integration test and deployment check against a real parser and model

| | |
|---|---|
| **Opened** | 2026-11-12 |
| **Status** | shipped |
| **Kind** | infra |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Every parser test stubs Ollama and PaddleOCR. Two production regressions passed them: the Gemini SDK switching to API v1 (WORK-0005) and keep_alive "-1" rejected by Ollama (WORK-0008); both turned every parse into a fallback while still answering 200. Nothing checks, before or after a deploy, that a real receipt goes in and the right fields come out of the intended backend.

## Decision

- `tests/test_integration.py`, marked `integration` and skipped unless `PARSER_URL` is set, talks HTTP to a running parser: health reports the vision model available; the public sample receipt (`receipts/small-receipt.png`) is answered **by the vision model, not the fallback**, with total 24.10, at least 3 items and inside the deadline; a non-image is a 400; a blank image ends as a handled answer (not a 500).
- `scripts/verify-deployment.sh [URL]` runs those tests from the built image on the parser's network; used against a candidate container before a deploy and against `receipt-parser-app` after it. AGENTS.md says so.
- expense-api gets a contract test: a response captured from the real parser goes through `transformResponse`.

Only the public sample receipts are used; no user receipts.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| HTTP tests against a running parser | One test for pre- and post-deploy; real model, OCR and network | Needs a running stack; slower (about a minute) | ✓ |
| More stubs | Fast | Both regressions passed stubs | ✗ |

## Consequences

**Positive:** a backend that silently falls back fails the check.

**Negative / Trade-offs accepted:** the check takes about a minute and loads the model.

**Risks / Open questions:** model answers can drift; assertions stick to what the sample receipt prints clearly (total, item count).

## Definition of done

- [x] Integration tests and `scripts/verify-deployment.sh`; fail on today's keep_alive bug, pass on the fix
- [x] Run against production
- [x] expense-api contract test from a captured parser response

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 building — owner asked whether integration tests exist; none do against a real model.
- 2026-11-12 verified — against production (`7240bc1`): 4 passed in 20 s. Against a candidate built from `83dd552` (before the keep_alive fix): `test_the_sample_receipt_is_read_by_the_intended_backend` failed (vision model 400, parse fell back), the other 3 passed. Default `pytest` still 29 passed, integration tests skipped without `PARSER_URL`. expense-api WORK-0078 adds the contract test.
- 2026-11-12 shipped — tests and script merged; documented in AGENTS.md and RELEASING.md.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
