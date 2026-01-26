#!/bin/bash
set -e

echo "=================================================="
echo "Receipt Parser - PaddleOCR + Ollama"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Starting services with Docker Compose...${NC}"
docker compose up -d

echo ""
echo -e "${YELLOW}Step 2: Waiting for Ollama service to be ready...${NC}"
max_attempts=30
attempt=0

while ! docker exec receipt-ollama ollama list > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "Error: Ollama service failed to start after $max_attempts attempts"
        exit 1
    fi
    echo "Waiting for Ollama... (attempt $attempt/$max_attempts)"
    sleep 2
done

echo -e "${GREEN}✓ Ollama service is ready${NC}"

echo ""
echo -e "${YELLOW}Step 3: Ensuring Qwen 2.5:7b model is available...${NC}"
if docker exec receipt-ollama ollama list | grep -q "qwen2.5:7b"; then
    echo -e "${GREEN}✓ Qwen 2.5:7b model already available${NC}"
else
    echo "Pulling Qwen 2.5:7b model (this may take a few minutes)..."
    docker exec receipt-ollama ollama pull qwen2.5:7b
    echo -e "${GREEN}✓ Qwen 2.5:7b model downloaded${NC}"
fi

echo ""
echo -e "${YELLOW}Step 4: Waiting for parser service to be ready...${NC}"
max_attempts=60
attempt=0

while ! curl -f http://localhost:8000/health > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "Error: Parser service failed to start after $max_attempts attempts"
        echo "Check logs with: docker compose logs parser"
        exit 1
    fi
    echo "Waiting for parser service... (attempt $attempt/$max_attempts)"
    sleep 2
done

echo -e "${GREEN}✓ Parser service is ready${NC}"

echo ""
echo "=================================================="
echo -e "${GREEN}Receipt Parser is ready!${NC}"
echo "=================================================="
echo ""
echo "API endpoints:"
echo "  - Health check:  http://localhost:8000/health"
echo "  - Service info:  http://localhost:8000/"
echo "  - Parse receipt: POST http://localhost:8000/parse"
echo "  - Parse batch:   POST http://localhost:8000/parse-batch"
echo ""
echo "Usage examples:"
echo "  1. Check health:"
echo "     curl http://localhost:8000/health"
echo ""
echo "  2. Parse a receipt:"
echo "     curl -X POST -F \"file=@receipts/sample.jpg\" http://localhost:8000/parse"
echo ""
echo "  3. View logs:"
echo "     docker compose logs -f parser"
echo ""
echo "  4. Stop services:"
echo "     docker compose down"
echo ""
echo "For testing, copy some receipt images to the ./receipts directory"
echo "Parsed results will be saved to ./output directory"
echo ""
