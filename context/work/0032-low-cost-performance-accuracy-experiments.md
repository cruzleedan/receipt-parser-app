---
id: 0032
title: "Benchmark low-cost image, extraction and inference improvements"
status: shipped
kind: spike
opened: 2026-11-17
decided: 2026-11-17
branch: fix/0017-parser-review-fixes
supersedes: ~
superseded-by: ~
---

# WORK-0032 — Benchmark low-cost image, extraction and inference improvements

| | |
|---|---|
| **Opened** | 2026-11-17 |
| **Status** | shipped |
| **Kind** | spike |
| **Supersedes** | — |
| **Superseded by** | — |

## Problem

The current local VLM is stronger on the owner's receipts than previously tested alternatives, but deployed benchmark accuracy remains imperfect and p90 latency is about 39 seconds. Several cheaper changes should be tested before paying for training or switching providers. The 2026-11-17 review also found correctness and measurement defects that must not be mistaken for model limitations.

## Decision

Implemented: run staged, local experiments using the [research report's ranked plan and adoption gates](../reviews/2026-11-17-code-review-and-research.md). First correct the scorer denominator (WORK-0029), baseline the production pipeline and resolve relevant parser defects. Compare image orientation/crops/resolution (1280/1600/1920), a field-only profile, and budgeted high-resolution field re-reads. Then, only if useful, test weight precision, Qwen3.5-9B, runtime settings and explicit lightweight OCR variants in isolation.

Record actual runtime/model versions, quality, latency, memory and all failures. The research report contains primary-source links and an illustrative cloud cost calculation; it does not authorize cloud receipt uploads, paid services, a production model switch or training. Preserve WORK-0008, WORK-0009, WORK-0011 and WORK-0016 decisions unless the owner changes them.

Results and decision: [implementation/experiment report](../reviews/2026-11-17-implementation-and-experiments.md). Preserve the current full-extraction model, image size and CPU text placement. Document the existing optional field-only profile; do not deploy the crop/resolution/re-read prototypes. Scheduling needs further evaluation in WORK-0035.

## Options considered

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Fix evidence loss and measure local image/profile changes first | No API fee; targets observed code and geometry weaknesses | Requires a held-out labelled sample | Yes |
| Immediately use a larger model or new OCR runtime | Possible quality improvement | Latency, memory and compatibility uncertain | Later experimental arm |
| Paid cloud escalation | Low illustrative per-receipt token cost | Data handling and accuracy need a separate decision | Research only |
| Fine-tune immediately | Could fit recurring layouts | Too few labels; training/export/quantization work | Continue existing WORK-0011 prerequisites |

## Consequences

**Positive:** chooses improvements from real receipt accuracy and user-visible latency instead of generic model rankings.

**Negative / Trade-offs accepted:** local compute and evaluation time; larger images and selective retries may increase latency.

**Risks / Open questions:** old labels have already influenced prompts; confidence thresholds may overfit; model swaps can evict the resident primary; newer Paddle/Ollama features may not work in pinned containers. No performance improvement is claimed until measured locally.

## Definition of done

- [x] Fixed-denominator baseline with exact totals, date/merchant coverage, missing results and model/runtime identity recorded; unavailable currency/item truth is explicitly disclosed.
- [x] Dataset handling and prior label reuse documented; no private data committed or uploaded, and no independent held-out accuracy claim made.
- [x] Geometry, simple cropping and field-only profile arms scored independently; EXIF behavior verified with synthetic orientation fixtures.
- [x] Bounded selective re-read prototype evaluated, including failed calls and high-confidence wrong dates; reject deployment rather than calibrating a policy from this tiny sample.
- [x] Additional model/runtime/OCR arms explicitly deferred with reasons; no paid/cloud or training work performed.
- [x] Warm median/p90/p95 and 1/2/4 request admission/health behavior reported; true VLM cold start explicitly deferred to avoid evicting the production model.
- [x] Recommendation supported by paired development results, limits and actual CPU/GPU memory/latency tradeoffs. Independent labels remain a prerequisite for any future accuracy-policy promotion.

## Log

- 2026-11-17 proposed — user requested performance/accuracy research at free or low price; primary-source research completed in the linked report. Local optimization experiments remain unrun.

- 2026-11-17 building — owner: "proceed"; implementing review fixes and local, no-fee experiments.

- 2026-11-17 study completed — 40 paired geometry/profile calls plus six bounded re-reads on eight previously used local labels; one date label unavailable. Field-only median 6.65 s vs 23.23 s; larger images timed out more often; selective re-read added latency without corrections. GPU vs CPU tested on public/fictional fixtures; CPU preserved.
- 2026-11-17 scope clarified — this spike ends with a no-promotion decision for new default accuracy policies. Fresh independent labels, calibrated retries, true cold-start eviction and additional models/runtimes remain future promotion gates, not claims satisfied by this development sample.

- 2026-11-17 shipped — owner-authorized fixes and local study completed; 85 unit checks passed, final candidate and production integration checks each 4 passed. Parser image 56d70051e9b6; repository utilities covered by focused regressions; context validation passed.

---

> **For AI agents:** Do NOT implement this work item unless status is
> `accepted` or `building`. If status is `proposed`, surface it to the user
> for a decision before writing any code. If status is `superseded`, follow
> the item in `superseded-by` instead. Surface contradictions with an
> accepted, building, shipped or operating decision before proceeding.
