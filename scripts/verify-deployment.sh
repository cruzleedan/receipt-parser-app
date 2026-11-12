#!/usr/bin/env bash
# WORK-0012: run the integration tests against a running parser, from the built image.
#   scripts/verify-deployment.sh                     # production: receipt-parser-app
#   scripts/verify-deployment.sh http://NAME:8000 NETWORK   # a candidate container
# Exit code is pytest's. Uses only the public sample receipts.
set -euo pipefail
cd "$(dirname "$0")/.."
URL=${1:-http://receipt-parser-app:8000}
NETWORK=${2:-receipt-parser-app_default}
IMAGE=${IMAGE:-receipt-parser-app-parser}
docker run --rm --network "$NETWORK" \
  -e PARSER_URL="$URL" -e EXPECTED_BACKEND="${EXPECTED_BACKEND:-vlm_ollama}" -e SAMPLE_DIR=/samples \
  -v "$PWD/tests:/app/tests:ro" -v "$PWD/pytest.ini:/app/pytest.ini:ro" -v "$PWD/receipts:/samples:ro" \
  --entrypoint python "$IMAGE" -m pytest -q -p no:cacheprovider -m integration
