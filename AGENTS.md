# Receipt Parser — Project Guide

Internal tool that parses receipt images into structured JSON data using OCR
and LLM extraction. Not publicly routed — accessible internally on port 8002.

**Stack:** Python · FastAPI · PaddleOCR · Ollama (local) or Google Gemini (cloud)  
**Access:** Internal only — `http://d3:8002` or via Tailscale

---

## Parser Backends

Two backends are supported, selected via the `PARSER_BACKEND` env var:

| Backend | Value | How it works |
|---|---|---|
| PaddleOCR + Ollama | `paddleocr_ollama` | OCR extracts text → Ollama LLM structures it as JSON (default) |
| Google Gemini | `gemini` | Sends image directly to Gemini Vision API; falls back to paddleocr_ollama on failure |

---

## Directory Structure

```
receipt-parser-app/
├── src/
│   ├── config.py           # Settings via pydantic-settings
│   ├── gemini_service.py   # Gemini Vision API backend
│   ├── llm_service.py      # Ollama LLM extraction service
│   └── __init__.py
├── docker/
│   └── Dockerfile
├── receipts/               # Input receipts (read-only mount)
├── output/                 # Parse results, only with SAVE_OUTPUT=true (debugging)
├── tests/
├── compose.yml
└── requirements.txt
```

---

## Networks

- Joins the external Docker network `shared-ollama-network` and the default network.
  `rag-network` is the local Compose key; `name: shared-ollama-network` selects
  the actual shared network.
- Accesses Ollama at `http://shared-ollama:11434` (set via `OLLAMA_HOST` env var)
- Start `ollama-service` or run the homelab bootstrap script to create the shared
  network before starting the parser.

---

## Common Commands

```bash
# Start (from receipt-parser-app/)
docker compose -f compose.yml up -d

# Logs
docker logs -f receipt-parser-app

# Rebuild after code changes
docker compose -f compose.yml up -d --build
```

---

## Critical Dependencies

- **Requires Ollama service running** when `PARSER_BACKEND=paddleocr_ollama`
- **Requires `GEMINI_API_KEY`** in `.env` when `PARSER_BACKEND=gemini`
- `receipts/` is a read-only volume mount — do not modify contents from within the container

## Checklist for New Code

- [ ] Backend selection controlled via `PARSER_BACKEND` env var (not hardcoded)
- [ ] `OLLAMA_HOST` read from environment
- [ ] New parser backends follow the fallback pattern (see `gemini_service.py`)
- [ ] No parse results kept on disk unless `SAVE_OUTPUT=true` (local debugging only, WORK-0002)

---

## Context

Architectural decisions and proposals live in `context/work/` (see
`context/work/0001-paddleocr-ollama-two-stage-pipeline.md` for why the
two-stage OCR→LLM architecture was chosen). Release conventions are in
`context/RELEASING.md`. Log framework friction (not code bugs) in
`context/friction.md`.
