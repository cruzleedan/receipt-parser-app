---
id: 0005
title: "One deadline per parse, and parsing off the event loop"
status: building
kind: fix
opened: 2026-11-11
decided: 2026-11-11
branch: fix/0005-parse-deadline
supersedes: ~
superseded-by: ~
---

# WORK-0005 — One deadline per parse, and parsing off the event loop

| | |
|---|---|
| **Opened** | 2026-11-11 |
| **Status** | building |
| **Kind** | fix |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

A `/parse` request has no overall limit. `GEMINI_TIMEOUT` (60) is read into settings but never passed to the Gemini client, so a hung Gemini call waits indefinitely; it is tried twice, then the fallback runs PaddleOCR and up to three Ollama calls of `OLLAMA_TIMEOUT` (120 s) each. The caller (expense-api) gives up long before, so the work is wasted and the caller cannot tell a timeout from an outage.

PaddleOCR (`extract_text`) and the Ollama call (`requests.post`) are also synchronous inside `async` handlers, so a parse blocks the single-worker server: `/health` and other requests wait until it ends.

Measured 2026-11-11 on d3: Gemini 7.7 s; local fallback 11–30 s; two Gemini 503s cost about 12 s.

## Decision

- `PARSE_DEADLINE_SECONDS` (default 70) bounds the whole request; past it the parser answers **504** `{"error": "Parse deadline exceeded"}`. This is the innermost budget of expense-api WORK-0073 (API 80 s, web 90 s, Cloudflare 100 s).
- Gemini gets a per-attempt HTTP timeout (`GEMINI_TIMEOUT`, default 20 s) and is tried only while at least `FALLBACK_RESERVE_SECONDS` (default 35) remain, so the local fallback always gets time to run.
- Ollama calls are bounded by the time left, not a fixed 120 s each.
- OCR and Ollama calls run in a worker thread (`asyncio.to_thread`), so `/health` answers during a parse.
- `pytest` tests cover the deadline, the reserve rule and the 504, with the backends stubbed.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| One deadline with a fallback reserve | Caller's budget is respected; fallback still runs | More moving parts | ✓ |
| Only lower each timeout | Small change | Sum of retries still exceeds the caller's budget | ✗ |

## Consequences

**Positive:** every parse ends inside the caller's budget with a distinct timeout answer; health checks stay responsive.

**Negative / Trade-offs accepted:** a thread that is still running after the deadline finishes in the background (Python threads cannot be cancelled); its result is discarded.

**Risks / Open questions:** none.

## Definition of done

- [x] Deadline, Gemini timeout, reserve rule and 504 implemented; blocking calls in threads
- [x] `pytest` passes in the image
- [ ] Deployed on d3; a real parse succeeds and `/health` answers during a parse

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-11 building — owner asked for work items for the review's findings and to build, merge and deploy them to production (with expense-api WORK-0072/0073).
- 2026-11-11 implemented and verified — `PARSE_DEADLINE_SECONDS` 70 (504), `GEMINI_TIMEOUT` 20 applied through `HttpOptions`, `FALLBACK_RESERVE_SECONDS` 35, Ollama bounded by the time left, OCR and Ollama in threads. `tests/test_parse_deadline.py`: 6 passed in the rebuilt image (504 within 2 s, `/health` under 1 s during a 1.5 s blocking OCR, Gemini skipped inside the reserve, attempts bounded, no Ollama call after the deadline).
- 2026-11-11 regression on deploy — passing `HttpOptions` made the Gemini SDK use API `v1`, which rejects JSON mode (400 INVALID_ARGUMENT), so parses fell back to the local pipeline (still 200). The pre-deploy image had already been replaced by the test rebuild, so no rollback image. Fixed forward: `api_version="v1beta"` set explicitly, test asserts it; a real Gemini call from the rebuilt image returned the receipt.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
