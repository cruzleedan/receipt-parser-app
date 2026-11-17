# Receipt Parser API

A high-performance receipt parser using a two-stage architecture: **PaddleOCR** for text extraction and **Ollama** (llama3.2) for structured JSON generation.

## Features

- **Two-stage pipeline**: OCR → LLM → JSON (optimized for speed and accuracy)
- **PaddleOCR PP-OCRv4**: Best-in-class OCR with low character error rate
- **Ollama + llama3.2**: Reliable JSON generation with structured output
- **FastAPI**: Modern async web framework
- **Docker Compose**: Easy deployment with shared Ollama network
- **Batch processing**: Process multiple receipts in one request
- **Field selection**: Choose which fields to extract per request

## Performance

| Metric | Value |
|--------|-------|
| Processing Time | 2-3s per receipt |
| Memory Limit | 4GB (2GB reserved) |
| CPU Limit | 4 cores |
| Startup Time | ~60s (model warm-up) |

## Architecture

```
Receipt Image → PaddleOCR (OCR) → Structured Text → Ollama (LLM) → JSON Output
```

**Stage 1: Text Extraction (PaddleOCR)**
- Orientation/unwarping disabled for typical upright receipt images
- Results returned in reading order (top-to-bottom, left-to-right)
- Average confidence score reported per request

**Stage 2: JSON Structuring (Ollama)**
- llama3.2 model via shared Ollama container
- Temperature=0 for deterministic output
- JSON mode enforced; markdown fallback extraction included
- OCR text capped at 4000 chars before prompt injection

## Quick Start

### Prerequisites

- Docker and Docker Compose
- External Docker networks: `shared-ollama-network` (shared with Ollama container)
- 4GB+ RAM available for the container

### Installation

1. Ensure the `shared-ollama-network` Docker network exists and Ollama is running on it with the `llama3.2-gpu:latest` model loaded.

2. Start the parser:
   ```bash
   docker compose up -d
   ```

3. The API will be available at `http://localhost:8002` (external) / `http://receipt-parser-app:8000` (internal Docker network).

### Testing

**Parse a single receipt:**
```bash
python test_api.py receipts/receipt-image.jpg
```

**Parse all receipts in a directory:**
```bash
python test_api.py receipts/
```

**Run performance benchmark:**
```bash
python test_api.py receipts/ --benchmark
```

**Batch processing:**
```bash
python test_api.py receipts/ --batch
```

## API Documentation

### Endpoints

#### GET /
Returns service information.

```bash
curl http://localhost:8002/
```

**Response:**
```json
{
  "name": "Receipt Parser API",
  "version": "1.0.0",
  "description": "Two-stage receipt parser using PaddleOCR + Ollama",
  "architecture": "PaddleOCR (OCR) → Ollama (LLM) → JSON"
}
```

#### GET /health
Health check endpoint.

```bash
curl http://localhost:8002/health
```

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "ocr": {
      "status": "ready",
      "backend": "PaddleOCR PP-OCRv4",
      "gpu_enabled": false
    },
    "llm": {
      "status": "connected",
      "backend": "Ollama",
      "model": "llama3.2-gpu:latest"
    }
  },
  "timestamp": "2026-01-25T10:30:00Z"
}
```

#### POST /parse
Parse a single receipt image.

**Accepted file types:** JPEG, PNG, GIF, WebP, BMP, TIFF

```bash
curl -X POST -F "file=@receipts/receipt-image.jpg" \
  http://localhost:8002/parse
```

**Field-selection query parameters** (all optional):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `items` | `true` | Extract line items |
| `date` | `true` | Extract transaction date |
| `time` | `true` | Extract transaction time |
| `subtotal` | `true` | Extract subtotal |
| `tax` | `true` | Extract tax amount |
| `tip` | `false` | Extract tip/gratuity |
| `discount` | `false` | Extract discount amount |
| `payment_method` | `false` | Extract payment method |
| `merchant_address` | `false` | Extract merchant address |
| `merchant_phone` | `false` | Extract merchant phone |
| `receipt_number` | `false` | Extract receipt/transaction number |
| `cashier` | `false` | Extract cashier name |

Example with extra fields:
```bash
curl -X POST \
  "http://localhost:8002/parse?tip=true&payment_method=true&receipt_number=true" \
  -F "file=@receipts/receipt-image.jpg"
```

**Response:**
```json
{
  "merchant_name": "Corner Store",
  "merchant_address": null,
  "merchant_phone": null,
  "date": "2026-01-25",
  "time": "14:30",
  "items": [
    {
      "name": "Milk",
      "quantity": 1,
      "unit_price": 3.99,
      "total_price": 3.99
    }
  ],
  "subtotal": 8.99,
  "tax": 0.72,
  "tip": null,
  "discount": null,
  "total": 9.71,
  "payment_method": null,
  "card_last_4": null,
  "receipt_number": null,
  "cashier": null,
  "processing_metadata": {
    "ocr_time_ms": 850,
    "llm_time_ms": 1200,
    "total_time_ms": 2100,
    "ocr_confidence": 0.94
  }
}
```

#### POST /parse-batch
Parse multiple receipts in one request. Supports the same field-selection query parameters as `/parse`.

```bash
curl -X POST \
  "http://localhost:8002/parse-batch?tip=true" \
  -F "files=@receipts/receipt1.jpg" \
  -F "files=@receipts/receipt2.jpg"
```

**Response:**
```json
{
  "results": [
    {
      "filename": "receipt1.jpg",
      "success": true,
      "data": { }
    },
    {
      "filename": "receipt2.jpg",
      "success": false,
      "error": "No text detected"
    }
  ],
  "total": 2,
  "successful": 1,
  "failed": 1,
  "processing_time_ms": 4200
}
```

## Configuration

Copy `.env.example` to `.env` and customize. The most important variables:

```bash
# OCR Configuration
OCR_USE_GPU=false                  # true to enable GPU acceleration for both OCR and LLM
OCR_LANG=en                        # Language (en, multilingual, etc.)

# Ollama Configuration
OLLAMA_HOST=http://shared-ollama:11434
OLLAMA_MODEL=llama3.2-gpu:latest   # Model name — must be pulled in Ollama
OLLAMA_TIMEOUT=120                 # Request timeout (seconds)

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# Performance
BATCH_MAX_SIZE=10                  # Max receipts per batch request
```

> **Note:** `OCR_USE_GPU` controls GPU acceleration for both PaddleOCR and the Ollama LLM call (`num_gpu`). Set to `false` for CPU-only deployments.

## Development

### Local Development (without Docker)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start Ollama separately and pull the model:
   ```bash
   ollama serve
   ollama pull llama3.2-gpu:latest
   ```

3. Copy and edit config:
   ```bash
   cp .env.example .env
   # Set OLLAMA_HOST=http://localhost:11434
   ```

4. Run the API:
   ```bash
   uvicorn src.main:app --reload
   ```

### Project Structure

```
receipt-parser-app/
├── src/
│   ├── main.py              # FastAPI application and endpoints
│   ├── ocr_service.py       # PaddleOCR wrapper
│   ├── llm_service.py       # Ollama client (async)
│   ├── models.py            # Pydantic schemas
│   ├── config.py            # Configuration via pydantic-settings
│   └── utils.py             # Image loading utilities
├── docker/
│   └── Dockerfile           # Parser service image
├── receipts/                # Input directory (mounted read-only)
├── output/                  # Output JSON files
├── compose.yml              # Docker Compose (connects to shared-ollama-network)
├── requirements.txt
├── .env.example
└── test_api.py
```

## Docker Commands

**Start services:**
```bash
docker compose up -d
```

**View logs:**
```bash
docker compose logs -f parser
```

**Stop services:**
```bash
docker compose down
```

**Rebuild after code changes:**
```bash
docker compose up -d --build
```

**Access container shell:**
```bash
docker exec -it receipt-parser-app bash
```

## Troubleshooting

### Service won't start

Check logs:
```bash
docker compose logs parser
```

### Ollama model not found

Pull the model in your Ollama container:
```bash
docker exec <ollama-container> ollama pull llama3.2-gpu:latest
```

### Out of memory

Reduce resource limits in `compose.yml` or use a smaller model:
```bash
OLLAMA_MODEL=llama3.2:1b
```

### Slow parsing

- Enable GPU acceleration: `OCR_USE_GPU=true`
- Use a smaller Ollama model
- Verify Ollama `keep_alive` is keeping the model loaded between requests

### Low accuracy

- Use higher quality images (clear, well-lit)
- Try multilingual OCR: `OCR_LANG=multilingual`
- Use a larger Ollama model for better JSON extraction

## Integration with expense-api

expense-api calls `/parse` with `multipart/form-data`. The parser is reached at `http://receipt-parser-app:8000` via the shared Docker network. Both services must be on `shared-ollama-network`.

Supported MIME types from expense-api: `image/jpeg`, `image/png`, `image/gif`, `image/webp`. PDF receipts are not supported by the parser — they will be rejected with HTTP 400.

## License

See LICENSE file for details.

### Capacity, limits and readiness (WORK-0017–0031)

`/parse` and `/parse-batch` share backend selection, fallback order, image validation
and extraction options. One request is admitted at a time by default; additional
requests receive **503** with `Retry-After: 2`. CPU image/OCR work has one bounded
worker. A timed-out job keeps that worker occupied until it finishes, preventing
successive timeouts from creating a backlog.

`/health` provides HTTP 200 diagnostics. **`/ready` returns 503 unless OCR and all
configured primary/fallback model dependencies are ready**; Docker uses `/ready`.
Readiness probes run concurrently and do not block the event loop. The unused
Gemini backend checks configuration without making billable inference calls. Models must
match the configured tag; another tag in the same family does not satisfy readiness.

Defaults (overridable through environment variables):

| Setting | Default | Behavior |
|---|---|---|
| `MAX_ACTIVE_PARSES` | 1 | Admission limit per API process; run one API worker for the shared OCR engine. |
| `MAX_UPLOAD_BYTES` | 10 MiB | Per image; checked before and during reads. |
| `MAX_REQUEST_BYTES` | 105 MiB | Absolute multipart request ceiling, also bounded by batch size and per-file budget. |
| `MAX_IMAGE_PIXELS` | 24,000,000 | Checked before eager decoding. |
| `INGRESS_TIMEOUT_SECONDS` | 15 | Upload body deadline, including multipart ingress. |
| `PARSE_DEADLINE_SECONDS` | 70 | Starts at ingress, includes image preparation and inference. |
| `BATCH_DEADLINE_SECONDS` | 70 | Whole sequential batch budget; completed results are preserved, remaining files marked failed. |
| `HEALTH_TIMEOUT_SECONDS` | 6 | Budget per concurrently executed dependency probe. |
| `OLLAMA_NUM_CTX` | 12,288 | Text fallback context. Input is never silently truncated. |
| `OLLAMA_NUM_PREDICT` | 2,048 | Text fallback output limit. |
| `OLLAMA_NUM_GPU` | unset | Let Ollama place the text model automatically; independent of CPU OCR. |
| `OCR_DEVICE` | derived from `OCR_USE_GPU` | Explicit Paddle device, e.g. `cpu` or `gpu:0`. |
| `VLM_NUM_CTX` / `VLM_NUM_PREDICT` | 8,192 / 2,048 | Vision context and output limits. |

Too-large input returns **413**; slow upload returns **408**; parse budget exhaustion
returns **504**. Batch errors are reported per file. Long OCR text that cannot fit
its conservative UTF-8 byte/token upper bound returns a handled extraction failure
instead of losing its footer. All backends reject token-truncated JSON, boolean and
non-finite money. Zero and refund amounts are supported. Currency and date
normalization are shared. `extraction_warnings` reports discarded unreadable line
items; callers should still confirm extracted data before saving.

For a field-only request use
`/parse?items=false&time=false&subtotal=false&tax=false`. This profile is optional;
normal requests continue to ask for line items. Local geometry/profile research
is tracked in `context/work/0032-low-cost-performance-accuracy-experiments.md`.
Raw benchmark answers stay outside the repository.
Compose explicitly defaults `OLLAMA_NUM_GPU=0` to preserve CPU text inference: the
corrected pipeline's GPU trial used about 9.5 GiB reported GPU allocation for only
a modest latency improvement on the two fixtures. Set this independently of OCR
when an isolated benchmark justifies a different placement.

`processing_metadata.backend` and `.model` identify the backend that actually
answered (`vlm_ollama`, `paddleocr_ollama` or `gemini`), including fallback.
PaddleOCR model assets persist in the `parser-ocr-models` volume across rebuilds;
new installations still need the initial model download. This volume contains
model assets, not receipt images or extraction results.
