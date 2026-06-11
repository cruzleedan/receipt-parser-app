# Implementation Plan: PaddleOCR + Ollama Receipt Parser

## Overview

Create a new receipt parser at `~/projects/receipt-parser-app` using a two-stage architecture (PaddleOCR → Ollama) to replace the existing Qwen 2.5-VL implementation. The new system prioritizes **speed and accuracy** while reducing resource footprint from 15GB to ~7GB total and processing time from 5-10s to 2-3s per receipt.

## Architecture

### Two-Stage Pipeline
```
Receipt Image → PaddleOCR (Stage 1: OCR) → Structured Text → Ollama (Stage 2: LLM) → JSON Output
```

**Stage 1: Text Extraction (PaddleOCR)**
- PP-OCRv4 model (English + multilingual)
- Image preprocessing: contrast, denoise, sharpen, binarization
- Spatial text organization (top-to-bottom, left-to-right)
- Confidence filtering
- **Target: 0.5-1s processing time**

**Stage 2: JSON Structuring (Ollama)**
- Qwen2.5:7b model via Ollama
- Structured output with JSON schema enforcement
- Temperature=0 for deterministic output
- Retry logic with validation
- **Target: 1-2s processing time**

## Technology Stack

- **PaddleOCR**: PP-OCRv4 (15.84% CER on receipts, best-in-class)
- **Ollama**: Local LLM inference engine
- **Qwen2.5:7b**: Superior JSON generation, structured data tasks
- **FastAPI**: Async web framework
- **Docker Compose**: Two-container deployment (Parser + Ollama)

## Project Structure

```
~/projects/receipt-parser-app/
├── src/
│   ├── main.py              # FastAPI app, endpoints, pipeline orchestration
│   ├── ocr_service.py       # PaddleOCR wrapper, image preprocessing
│   ├── llm_service.py       # Ollama client, JSON structuring
│   ├── models.py            # Pydantic models, JSON schema
│   ├── config.py            # Configuration management
│   └── utils.py             # Image preprocessing helpers
├── tests/
│   ├── test_ocr.py          # OCR unit tests
│   ├── test_llm.py          # LLM unit tests
│   ├── test_api.py          # API integration tests
│   └── fixtures/            # Sample receipts for testing
├── docker/
│   ├── Dockerfile           # Parser service image
│   └── docker-compose.yml   # Two-service orchestration
├── receipts/                # Input directory (test images)
├── output/                  # Parsed JSON outputs
├── requirements.txt         # Python dependencies
├── .env.example             # Configuration template
├── quickstart.sh            # Startup script
└── README.md
```

## Implementation Steps

### 1. Project Setup
- Create directory structure at `~/projects/receipt-parser-app`
- Initialize `requirements.txt` with dependencies:
  - paddleocr, paddlepaddle
  - requests (Ollama client)
  - fastapi, uvicorn, python-multipart
  - pydantic, pillow, numpy, opencv-python

### 2. Core Services

#### OCR Service (`src/ocr_service.py`)
```python
class ReceiptOCRService:
    - __init__(use_gpu=True): Initialize PaddleOCR with optimized config
    - preprocess_image(image): CLAHE, denoise, sharpen, binarize
    - extract_text(image): Run OCR, organize spatially, return OCRResult
    - extract_batch(images): Parallel processing with ThreadPoolExecutor
```

**Key Configuration:**
- `use_angle_cls=True` (handle rotated receipts)
- `det_db_thresh=0.3` (lower threshold for small text)
- `rec_batch_num=6` (batch recognition)

#### LLM Service (`src/llm_service.py`)
```python
class OllamaLLMService:
    - __init__(host, model="qwen2.5:7b"): Initialize Ollama client
    - parse_receipt(ocr_text): Generate JSON via Ollama API
    - validate_response(response): Validate against schema
    - _build_prompt(ocr_text): Structured prompt with JSON schema
```

**Prompt Template:**
```
System: You are a receipt parsing expert. Extract structured data from OCR text.

User: Parse this receipt OCR text into JSON:
{ocr_text}

Required JSON schema: {schema}

Instructions:
- Match merchant name from header
- Parse date as YYYY-MM-DD
- Extract all line items with quantities and prices
- Use null for missing fields
```

**Ollama Configuration:**
- `temperature=0.0` (deterministic)
- `format="json"` (structured output mode)
- `num_predict=512` (max tokens)

#### Main Application (`src/main.py`)
```python
@app.get("/") - Service info
@app.get("/health") - Health check with service status
@app.post("/parse") - Single receipt parsing
@app.post("/parse-batch") - Batch processing (parallel OCR, sequential LLM)
```

**Pipeline Flow:**
1. Validate image upload
2. OCR extraction (0.5-1s)
3. LLM structuring (1-2s)
4. Response validation
5. Save to output/ (optional)
6. Return JSON

#### Models (`src/models.py`)
```python
class ReceiptItem(BaseModel):
    name: str
    quantity: int = 1
    unit_price: float | None = None
    total_price: float

class ReceiptData(BaseModel):
    merchant_name: str
    merchant_address: str | None = None
    date: str  # YYYY-MM-DD
    time: str | None = None
    items: List[ReceiptItem]
    subtotal: float | None = None
    tax: float | None = None
    total: float
    payment_method: str | None = None
    # ... (match existing API schema)
```

### 3. Docker Deployment

#### docker-compose.yml (Two-Container Architecture)
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: ["ollama-models:/root/.ollama"]
    healthcheck: ["CMD", "ollama", "list"]
    deploy:
      resources:
        limits: {cpus: '8', memory: 8G}

  parser:
    build: {context: ., dockerfile: docker/Dockerfile}
    depends_on: {ollama: {condition: service_healthy}}
    ports: ["8000:8000"]
    volumes:
      - ./receipts:/app/receipts:ro
      - ./output:/app/output
    environment:
      - OLLAMA_HOST=http://ollama:11434
      - OLLAMA_MODEL=qwen2.5:7b
    deploy:
      resources:
        limits: {cpus: '4', memory: 4G}

volumes:
  ollama-models:
```

#### Dockerfile
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgomp1 libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgl1-mesa-glx curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
RUN mkdir -p /app/receipts /app/output

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### quickstart.sh
```bash
#!/bin/bash
set -e

docker-compose up -d
# Wait for Ollama, pull model, wait for parser
docker exec receipt-ollama ollama pull qwen2.5:7b
# Health check loop
echo "✓ Receipt Parser ready at http://localhost:8000"
```

### 4. Testing

**Unit Tests:**
- `test_ocr_service.py`: Image preprocessing, text extraction, spatial ordering
- `test_llm_service.py`: Prompt generation, JSON parsing, validation
- `test_api_endpoints.py`: FastAPI endpoints

**Integration Tests:**
- End-to-end pipeline with fixture receipts
- Error handling (blurry images, rotated, multilingual)
- Batch processing throughput

**Test Fixtures:**
```
tests/fixtures/receipts/
├── grocery_simple.jpg       # Clean receipt
├── restaurant_complex.jpg   # Multi-column
├── receipt_rotated.jpg      # Rotation test
└── receipt_blurry.jpg       # Low quality
```

## API Compatibility

Maintains 100% compatibility with existing API:

| Endpoint | Method | Compatible |
|----------|--------|------------|
| `/` | GET | ✓ |
| `/health` | GET | ✓ (extended) |
| `/parse` | POST | ✓ |
| `/parse-batch` | POST | ✓ |

**JSON Output Schema:**
```json
{
  "merchant_name": "string",
  "merchant_address": "string | null",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "items": [{"name": "string", "quantity": 1, "unit_price": 0.0, "total_price": 0.0}],
  "subtotal": 0.0,
  "tax": 0.0,
  "total": 0.0,
  "payment_method": "string | null",
  "processing_metadata": {
    "ocr_time_ms": 850,
    "llm_time_ms": 1200,
    "total_time_ms": 2100
  }
}
```

## Performance Targets

| Metric | Target | Current (Qwen) | Improvement |
|--------|--------|----------------|-------------|
| Processing Time | 2-3s | 5-10s | 2-3x faster |
| Memory Usage | 4-6GB | 12-15GB | 60% reduction |
| Startup Time | 10-15s | 30-60s | 3x faster |
| Container Size | 7GB | 18GB | 60% reduction |
| Accuracy | 90%+ | 85% | +5% |

**Optimization Strategies:**
- Parallel OCR for batch processing (ThreadPoolExecutor)
- Image preprocessing pipeline (CLAHE, denoise, sharpen)
- GPU acceleration for PaddleOCR (optional)
- Ollama structured output mode (reduces parsing errors)
- Connection pooling for Ollama API

## Configuration

**.env.example:**
```bash
# OCR Configuration
OCR_USE_GPU=false
OCR_LANG=en,multilingual
OCR_DET_THRESH=0.3

# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT=30

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Performance
BATCH_MAX_SIZE=10
MAX_IMAGE_SIZE=4096
```

## Critical Files

1. **src/ocr_service.py** - PaddleOCR integration, image preprocessing
2. **src/llm_service.py** - Ollama client, JSON structuring
3. **src/main.py** - FastAPI app, pipeline orchestration
4. **src/models.py** - Pydantic schemas, validation
5. **docker/docker-compose.yml** - Two-service deployment
6. **docker/Dockerfile** - Parser service image
7. **requirements.txt** - Python dependencies

## Verification

### End-to-End Testing

1. **Start Services:**
   ```bash
   cd ~/projects/receipt-parser-app
   ./quickstart.sh
   ```

2. **Health Check:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy", "services": {...}}
   ```

3. **Parse Single Receipt:**
   ```bash
   curl -X POST -F "file=@receipts/sample.jpg" \
     http://localhost:8000/parse
   # Verify JSON structure matches schema
   ```

4. **Parse Batch:**
   ```bash
   curl -X POST -F "files=@receipts/r1.jpg" -F "files=@receipts/r2.jpg" \
     http://localhost:8000/parse-batch
   # Verify: {"results": [...], "total": 2}
   ```

5. **Run Test Suite:**
   ```bash
   pytest tests/ -v --cov=src
   # Target: >80% coverage
   ```

6. **Performance Benchmark:**
   ```bash
   python test_api.py receipts/ --benchmark
   # Verify: avg processing time < 3s
   ```

7. **Verify Output:**
   - Check `output/` directory for saved JSON files
   - Validate JSON structure matches schema
   - Verify accuracy against ground truth

### Success Criteria

✓ All endpoints functional
✓ Processing time < 3s (95th percentile)
✓ Memory usage < 8GB total
✓ Accuracy ≥ 85% on test fixtures
✓ Docker deployment working
✓ Test coverage > 80%
✓ API compatibility maintained

## Migration Notes

**Seamless Switchover:**
```bash
# Stop old service
docker-compose -f ~/projects/receipt-parser/docker-compose.yml down

# Start new service
docker-compose -f ~/projects/receipt-parser-app/docker-compose.yml up -d
```

**API Compatibility:** Clients require zero changes - same endpoints, request/response formats.

**Fallback Plan:** Keep existing Qwen service available for A/B testing or complex receipt fallback.
