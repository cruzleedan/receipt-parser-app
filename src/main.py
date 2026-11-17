"""
FastAPI application for receipt parsing using PaddleOCR + Ollama.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List
import json

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from src.models import (
    ReceiptData,
    ReceiptResponse,
    ProcessingMetadata,
    ParseError,
    BatchResult,
    BatchResponse,
    HealthResponse,
    ServiceInfo,
    ExtractionOptions,
)
from src.config import settings
from src.ocr_service import ReceiptOCRService
from src.llm_service import OllamaLLMService
from src.gemini_service import GeminiReceiptService
from src.vlm_service import VisionLLMService
from src.utils import load_image_from_bytes, ImageTooLarge
from src.workers import image_worker, CapacityError
from src.ingress import IngressMiddleware

import sys

# Reset any existing handlers that Uvicorn might have put there
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
# )
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)] # Force output to stdout
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Receipt Parser API",
    description="Two-stage receipt parser using PaddleOCR + Ollama",
    version="1.0.0",
)

app.add_middleware(IngressMiddleware)

# Global service instances
ocr_service: ReceiptOCRService = None
llm_service: OllamaLLMService = None
gemini_service: GeminiReceiptService = None
vlm_service: VisionLLMService = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global ocr_service, llm_service, gemini_service, vlm_service

    logger.info("Starting Receipt Parser API...")
    logger.info(f"Parser backend: {settings.parser_backend}")

    # Initialize Gemini service (if configured) - used as primary backend
    if settings.parser_backend == "gemini":
        try:
            gemini_service = GeminiReceiptService(
                api_key=settings.gemini_api_key, model=settings.gemini_model
            )
            logger.info("Gemini service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {e}")
            gemini_service = None

    if settings.parser_backend == "vlm_ollama":
        vlm_service = VisionLLMService()

    # Initialize OCR service (used as fallback, or as primary when not using Gemini)
    try:
        ocr_service = ReceiptOCRService(use_gpu=settings.ocr_use_gpu)
        logger.info("OCR service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize OCR service: {e}")
        raise

    # Initialize LLM service
    try:
        llm_service = OllamaLLMService(
            host=settings.ollama_host, model=settings.ollama_model
        )
        logger.info("LLM service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize LLM service: {e}")
        raise

    # Create output directory if parse results are kept (WORK-0002)
    if settings.save_output:
        Path(settings.output_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Receipt Parser API started successfully")


@app.get("/", response_model=ServiceInfo)
async def root():
    """Get service information."""
    return ServiceInfo()


@app.get("/health", response_model=HealthResponse)
async def health():
    """Diagnostic health stays HTTP 200; /ready is the readiness contract."""
    checks = {"ocr": ocr_service, "llm": llm_service}
    if settings.parser_backend == "vlm_ollama":
        checks["vlm"] = vlm_service
    if settings.parser_backend == "gemini":
        checks["gemini"] = gemini_service

    async def probe(service):
        if service is None:
            return {"status": "error", "error": "not initialized"}
        try:
            return await asyncio.wait_for(service.health_check(), settings.health_timeout_seconds)
        except Exception as exc:
            return {"status": "error", "error": str(exc) or "health deadline exceeded"}

    results = await asyncio.gather(*(probe(service) for service in checks.values()))
    services = dict(zip(checks, results))
    ready = services["ocr"].get("status") == "ready"
    for name, result in services.items():
        if name != "ocr":
            ready &= result.get("status") == "connected"
            if name in ("llm", "vlm"):
                ready &= result.get("model_available") is True
    return HealthResponse(status="healthy" if ready else "degraded", services=services,
                          timestamp=datetime.utcnow().isoformat() + "Z")


@app.get("/ready")
async def readiness():
    """Require primary and fallback models: a degraded fallback is not ready."""
    body = await health()
    return JSONResponse(body.model_dump(), status_code=200 if body.status == "healthy" else 503)


async def _parse_with_paddleocr_ollama(
    image, extraction_options: ExtractionOptions, start_time: float, deadline: float | None = None
):
    """
    Run the PaddleOCR + Ollama pipeline.

    Returns either a ReceiptResponse or a JSONResponse (for handled errors).
    Raises HTTPException for unrecoverable errors.
    """
    # Stage 1: OCR extraction
    ocr_start = time.time()
    try:
        # WORK-0005: CPU-bound OCR runs in a thread so /health stays responsive.
        ocr_result = await image_worker.run(ocr_service.extract_text, image)
    except CapacityError:
        raise
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"OCR extraction failed: {str(e)}"
        )
    ocr_time_ms = (time.time() - ocr_start) * 1000

    # Check if OCR found any text
    if not ocr_result.full_text.strip():
        return JSONResponse(
            status_code=422,
            content=ParseError(
                error="No text detected",
                details="OCR could not detect any text in the image",
                ocr_confidence=ocr_result.confidence,
            ).model_dump(),
        )

    # Stage 2: LLM structuring
    llm_start = time.time()
    try:
        receipt_data = await llm_service.parse_receipt(
            ocr_result.full_text, extraction_options=extraction_options, deadline=deadline
        )
    except TimeoutError:
        raise
    except Exception as e:
        logger.error(f"LLM parsing failed: {e}")
        return JSONResponse(
            status_code=422,
            content=ParseError(
                error="LLM parsing failed",
                details=str(e),
                ocr_text=ocr_result.full_text[:500],  # First 500 chars
                ocr_confidence=ocr_result.confidence,
            ).model_dump(),
        )
    llm_time_ms = (time.time() - llm_start) * 1000

    total_time_ms = (time.time() - start_time) * 1000

    metadata = ProcessingMetadata(
        backend="paddleocr_ollama", model=getattr(llm_service, "model", None),
        ocr_time_ms=ocr_time_ms,
        llm_time_ms=llm_time_ms,
        total_time_ms=total_time_ms,
        ocr_confidence=ocr_result.confidence,
    )

    return ReceiptResponse(**receipt_data.model_dump(), processing_metadata=metadata)


async def _parse_with_gemini(
    image, extraction_options: ExtractionOptions, start_time: float, deadline: float | None = None
):
    """
    Run the Gemini single-stage pipeline.

    Returns a ReceiptResponse on success, raises on failure (caller handles fallback).
    """
    receipt_data = await gemini_service.parse_receipt(
        image,
        extraction_options=extraction_options,
        deadline=deadline,
        reserve_seconds=settings.fallback_reserve_seconds,
    )

    total_time_ms = (time.time() - start_time) * 1000

    metadata = ProcessingMetadata(
        backend="gemini", model=getattr(gemini_service, "model", None),
        ocr_time_ms=0.0,
        llm_time_ms=total_time_ms,
        total_time_ms=total_time_ms,
        ocr_confidence=1.0,
    )

    return ReceiptResponse(**receipt_data.model_dump(), processing_metadata=metadata)


async def _run_backends(image, extraction_options: ExtractionOptions, start_time: float, deadline: float):
    """Gemini or the vision model first if configured, then PaddleOCR + Ollama, all before `deadline`."""
    if settings.parser_backend == "vlm_ollama" and vlm_service is not None:
        try:
            receipt = await vlm_service.parse_receipt(
                image, extraction_options=extraction_options, deadline=deadline,
                reserve_seconds=settings.vlm_fallback_reserve_seconds,
            )
            elapsed = (time.time() - start_time) * 1000
            logger.info("Receipt parsed using the vision model")
            return ReceiptResponse(
                **receipt.model_dump(),
                processing_metadata=ProcessingMetadata(
                    backend="vlm_ollama", model=getattr(vlm_service, "model", None),
                    ocr_time_ms=0.0, llm_time_ms=elapsed, total_time_ms=elapsed, ocr_confidence=1.0),
            )
        except CapacityError:
            raise
        except Exception as e:
            logger.warning(f"Vision model failed, falling back to PaddleOCR + Ollama: {type(e).__name__}: {str(e)[:200]}")
    if settings.parser_backend == "gemini" and gemini_service is not None:
        try:
            response = await _parse_with_gemini(image, extraction_options, start_time, deadline)
            logger.info("Receipt parsed using Gemini backend")
            return response
        except CapacityError:
            raise
        except Exception as e:
            logger.warning(f"Gemini parsing failed, falling back to PaddleOCR + Ollama: {e}")
    return await _parse_with_paddleocr_ollama(image, extraction_options, start_time, deadline)


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff"}


async def _parse_upload(file, options, deadline):
    started = time.time()
    async with asyncio.timeout_at(deadline):
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(400, f"Unsupported file type '{file.content_type}'")
        chunks, size = [], 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise HTTPException(413, "Image exceeds the upload byte limit")
            chunks.append(chunk)
        try:
            image = await image_worker.run(load_image_from_bytes, b"".join(chunks))
        except ImageTooLarge as exc:
            raise HTTPException(413, str(exc)) from exc
        except (CapacityError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise HTTPException(400, f"Invalid image file: {exc}") from exc
        # CPU jobs own the image until completion, including after cancellation.
        return await _run_backends(image, options, started, deadline)


def _deadline_error():
    return JSONResponse(status_code=504, content=ParseError(
        error="Parse deadline exceeded",
        details=f"No result within {settings.parse_deadline_seconds:g} seconds",
    ).model_dump())


@app.post("/parse")
async def parse_receipt(
    request: Request,
    file: UploadFile = File(...),
    items: bool = Query(True, description="Extract line items"),
    date: bool = Query(True, description="Extract transaction date"),
    time_field: bool = Query(True, alias="time", description="Extract transaction time"),
    subtotal: bool = Query(True, description="Extract subtotal"),
    tax: bool = Query(True, description="Extract tax amount"),
    tip: bool = Query(False, description="Extract tip amount"),
    discount: bool = Query(False, description="Extract discount amount"),
    payment_method: bool = Query(False, description="Extract payment method"),
    merchant_address: bool = Query(False, description="Extract merchant address"),
    merchant_phone: bool = Query(False, description="Extract merchant phone"),
    receipt_number: bool = Query(False, description="Extract receipt/transaction number"),
    cashier: bool = Query(False, description="Extract cashier name"),
):
    """
    Parse a single receipt image into structured JSON.

    Args:
        file: Receipt image file (JPG, PNG, etc.)
        items: Extract line items (default: true)
        date: Extract transaction date (default: true)
        time: Extract transaction time (default: true)
        subtotal: Extract subtotal (default: true)
        tax: Extract tax amount (default: true)
        tip: Extract tip amount (default: false)
        discount: Extract discount amount (default: false)
        payment_method: Extract payment method (default: false)
        merchant_address: Extract merchant address (default: false)
        merchant_phone: Extract merchant phone (default: false)
        receipt_number: Extract receipt/transaction number (default: false)
        cashier: Extract cashier name (default: false)

    Returns:
        ReceiptResponse with extracted data and metadata
    """
    # Build extraction options from query parameters
    extraction_options = ExtractionOptions(
        items=items,
        date=date,
        time=time_field,
        subtotal=subtotal,
        tax=tax,
        tip=tip,
        discount=discount,
        payment_method=payment_method,
        merchant_address=merchant_address,
        merchant_phone=merchant_phone,
        receipt_number=receipt_number,
        cashier=cashier,
    )

    deadline = request.state.parse_deadline
    try:
        response = await _parse_upload(file, extraction_options, deadline)
    except TimeoutError:
        return _deadline_error()
    except CapacityError as exc:
        raise HTTPException(503, str(exc), headers={"Retry-After": "2"}) from exc
    if isinstance(response, ReceiptResponse) and settings.save_output:
        from uuid import uuid4
        output_path = Path(settings.output_dir) / f"receipt_{uuid4().hex}.json"
        try:
            output_path.write_text(response.model_dump_json(indent=2))
        except OSError as exc:
            logger.warning("Could not save debug output: %s", exc)
    return response


@app.post("/parse-batch", response_model=BatchResponse)
async def parse_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    items: bool = Query(True, description="Extract line items"),
    date: bool = Query(True, description="Extract transaction date"),
    time_field: bool = Query(True, alias="time", description="Extract transaction time"),
    subtotal: bool = Query(True, description="Extract subtotal"),
    tax: bool = Query(True, description="Extract tax amount"),
    tip: bool = Query(False, description="Extract tip amount"),
    discount: bool = Query(False, description="Extract discount amount"),
    payment_method: bool = Query(False, description="Extract payment method"),
    merchant_address: bool = Query(False, description="Extract merchant address"),
    merchant_phone: bool = Query(False, description="Extract merchant phone"),
    receipt_number: bool = Query(False, description="Extract receipt/transaction number"),
    cashier: bool = Query(False, description="Extract cashier name"),
):
    """
    Parse multiple receipt images.

    Args:
        files: List of receipt image files
        (remaining params): Same field-selection query params as /parse

    Returns:
        BatchResponse with results for each receipt
    """
    extraction_options = ExtractionOptions(
        items=items,
        date=date,
        time=time_field,
        subtotal=subtotal,
        tax=tax,
        tip=tip,
        discount=discount,
        payment_method=payment_method,
        merchant_address=merchant_address,
        merchant_phone=merchant_phone,
        receipt_number=receipt_number,
        cashier=cashier,
    )

    started = time.monotonic()
    if len(files) > settings.batch_max_size:
        raise HTTPException(400, f"Batch size exceeds maximum ({settings.batch_max_size})")
    results = []
    batch_deadline = request.state.parse_deadline
    for file in files:
        if time.monotonic() >= batch_deadline:
            results.append(BatchResult(filename=file.filename or "upload", success=False,
                                       error="Batch deadline exceeded; receipt not processed"))
            continue
        deadline = min(batch_deadline, time.monotonic() + settings.parse_deadline_seconds)
        try:
            response = await _parse_upload(file, extraction_options, deadline)
            if isinstance(response, JSONResponse):
                error = json.loads(response.body).get("error", "Extraction failed")
                results.append(BatchResult(filename=file.filename or "upload", success=False, error=error))
            else:
                results.append(BatchResult(filename=file.filename or "upload", success=True,
                    data=ReceiptData.model_validate(response.model_dump())))
        except TimeoutError:
            results.append(BatchResult(filename=file.filename or "upload", success=False,
                                       error="Parse deadline exceeded"))
        except HTTPException as exc:
            results.append(BatchResult(filename=file.filename or "upload", success=False, error=str(exc.detail)))
        except CapacityError as exc:
            results.append(BatchResult(filename=file.filename or "upload", success=False, error=str(exc)))
        except Exception:
            logger.exception("Batch receipt failed")
            results.append(BatchResult(filename=file.filename or "upload", success=False,
                                       error="Receipt extraction failed"))
    successful = sum(result.success for result in results)
    return BatchResponse(results=results, total=len(results), successful=successful,
                         failed=len(results) - successful,
                         processing_time_ms=(time.monotonic() - started) * 1000)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
    )
