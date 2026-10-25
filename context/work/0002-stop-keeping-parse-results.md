---
id: 0002
title: "Stop keeping parse results on disk"
status: shipped
kind: fix
opened: 2026-10-25
decided: 2026-10-25
branch: ~
supersedes: ~
superseded-by: ~
---

# WORK-0002 — Stop keeping parse results on disk

| | |
|---|---|
| **Opened** | 2026-10-25 |
| **Status** | shipped |
| **Kind** | fix |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Every parse writes its result (the receipt's extracted fields as JSON) to `OUTPUT_DIR` (`/app/output` in the container) as `receipt_<timestamp>.json`, and nothing ever deletes them: 42 files in production since 2026-02. The caller (expense-api) already stores what it needs, so these are an unlisted second copy of users' receipt data, outside any retention policy (expense-api WORK-0048).

## Decision

Do not write parse results to disk by default. Keep the code path behind `SAVE_OUTPUT=true` for local debugging only (never set in production). Delete the existing files in production. Also cap the container's logs (`json-file`, `max-size: 10m`, `max-file: 5`, expense-api WORK-0057).

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Off by default, opt-in for debugging | No second copy; still debuggable locally | None | ✓ |
| Keep with an expiry | Debug history | Still a second copy of personal data | ✗ |

## Consequences

**Positive:** the service keeps no user data after answering.

**Negative / Trade-offs accepted:** no history of past parses in production.

**Risks / Open questions:** none.

## Definition of done

- [x] Output writing off unless SAVE_OUTPUT=true; test
- [x] Existing production files deleted
- [x] Log limits in compose
- [x] Redeployed; /app/output stays empty after a parse

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-10-25 accepted — gap found answering the Expense app's privacy questions (mailbox [410]).
- 2026-10-25 shipped — rebuilt and recreated (owner: deploy); logs capped
  (10 MB x 5); a parse of `receipts/receipt-image.jpg` answered 200 and wrote
  nothing; the 42 old `receipt_*.json` files deleted from `output/`. (No
  automated test suite exists in this repo; checked by hand.)

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
