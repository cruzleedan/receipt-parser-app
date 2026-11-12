---
id: 0013
title: "Daily integration check of the production parser, with a Healthchecks ping"
status: shipped
kind: infra
opened: 2026-11-12
decided: 2026-11-12
branch: infra/0013-daily-parser-check
supersedes: ~
superseded-by: ~
---

# WORK-0013 — Daily integration check of the production parser, with a Healthchecks ping

| | |
|---|---|
| **Opened** | 2026-11-12 |
| **Status** | shipped |
| **Kind** | infra |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

Parser regressions fail quietly: a broken vision model still answers 200 through the fallback (WORK-0005, WORK-0008 deploy). Real traffic is too low for anyone to notice soon, and d3 has no alerting (d3-homelab idea `email-alerting`, parked).

## Decision

`scripts/daily-check.sh` runs WORK-0012's `scripts/verify-deployment.sh` against production from the owner's crontab at 06:30 Asia/Manila (clear of the 03:xx backups and demo resets), logs one line to `~/receipt-parser-checks/check.log` (failing tests indented below), and, when `~/.config/receipt-parser-check.env` (mode 600) holds `PING_URL`, pings Healthchecks.io: `PING_URL` on success, `PING_URL/fail` on failure. Healthchecks emails the owner on a failure or a missing ping. This follows d3-learning's backup monitoring; the check itself is created by the owner in their Healthchecks account (daily period, grace a few hours).

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Cron + Healthchecks ping | Existing pattern; also alerts when d3 or cron is down | Owner creates the check | ✓ |
| Uptime Kuma on d3 | Covers every service | Parked idea; bigger | ✗ (not now) |
| Log only | No setup | Nobody reads it | ✗ |

## Consequences

**Positive:** a parser that silently falls back is noticed within a day.

**Negative / Trade-offs accepted:** one sample parse a day (about 20 s of GPU).

**Risks / Open questions:** until `PING_URL` is set, failures are only logged.

## Definition of done

- [x] Script and cron entry; success and failure paths checked
- [x] Owner adds the Healthchecks check and `PING_URL`; one success ping seen

## Log

<!-- Append-only. One line per status change or notable event. This is the
     audit trail — do not rewrite past entries. -->
- 2026-11-12 building — owner approved ("proceed") the recommendation to run the parser check daily.
- 2026-11-12 verified — against production: `exit=0 4 passed` logged; against a missing host (separate log): `exit=1 4 failed` with the errors below it. Cron line `30 6 * * * …/scripts/daily-check.sh` added to the owner's crontab. No `PING_URL` yet.
- 2026-11-12 shipped — owner created the Healthchecks check (daily, grace 3 h) and `~/.config/receipt-parser-check.env` (mode 600). Success ping sent; a deliberate failure (missing host, separate log) pinged `/fail` and the owner received the email; a passing run restored the check.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead — do NOT implement the pattern
> described here. If you are about to contradict an `accepted`, `building`,
> `shipped`, or `operating` item, stop and surface it to the user before
> proceeding.
