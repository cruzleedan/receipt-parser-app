"""
FastAPI application for receipt parsing using PaddleOCR + Ollama.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List
import json

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse

from src.models import (
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
from src.utils import load_image_from_bytes

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

# Global service instances
ocr_service: ReceiptOCRService = None
llm_service: OllamaLLMService = None
gemini_service: GeminiReceiptService = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global ocr_service, llm_service, gemini_service

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
    """Health check endpoint."""
    try:
        # Check OCR service
        ocr_status = await ocr_service.health_check()

        # Check LLM service
        llm_status = await llm_service.health_check()

        services = {"ocr": ocr_status, "llm": llm_status}

        # Overall status
        overall_status = "healthy"
        if ocr_status.get("status") != "ready" or llm_status.get("status") != "connected":
            overall_status = "degraded"

        # Check Gemini service (if configured as backend)
        if settings.parser_backend == "gemini":
            if gemini_service is not None:
                gemini_status = await gemini_service.health_check()
            else:
                gemini_status = {"status": "error", "backend": "Gemini", "error": "not initialized"}
            services["gemini"] = gemini_status
            if gemini_status.get("status") != "connected":
                overall_status = "degraded"

        return HealthResponse(
            status=overall_status,
            services=services,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            services={"error": str(e)},
            timestamp=datetime.utcnow().isoformat() + "Z",
        )


async def _parse_with_paddleocr_ollama(
    image, extraction_options: ExtractionOptions, start_time: float
):
    """
    Run the PaddleOCR + Ollama pipeline.

    Returns either a ReceiptResponse or a JSONResponse (for handled errors).
    Raises HTTPException for unrecoverable errors.
    """
    # Stage 1: OCR extraction
    ocr_start = time.time()
    try:
        ocr_result = ocr_service.extract_text(image)
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
            ).dict(),
        )

    # Stage 2: LLM structuring
    llm_start = time.time()
    try:
        receipt_data = await llm_service.parse_receipt(ocr_result.full_text, extraction_options=extraction_options)
    except Exception as e:
        logger.error(f"LLM parsing failed: {e}")
        return JSONResponse(
            status_code=422,
            content=ParseError(
                error="LLM parsing failed",
                details=str(e),
                ocr_text=ocr_result.full_text[:500],  # First 500 chars
                ocr_confidence=ocr_result.confidence,
            ).dict(),
        )
    llm_time_ms = (time.time() - llm_start) * 1000

    total_time_ms = (time.time() - start_time) * 1000

    metadata = ProcessingMetadata(
        ocr_time_ms=ocr_time_ms,
        llm_time_ms=llm_time_ms,
        total_time_ms=total_time_ms,
        ocr_confidence=ocr_result.confidence,
    )

    return ReceiptResponse(**receipt_data.dict(), processing_metadata=metadata)


async def _parse_with_gemini(
    image, extraction_options: ExtractionOptions, start_time: float
):
    """
    Run the Gemini single-stage pipeline.

    Returns a ReceiptResponse on success, raises on failure (caller handles fallback).
    """
    receipt_data = await gemini_service.parse_receipt(image, extraction_options=extraction_options)

    total_time_ms = (time.time() - start_time) * 1000

    metadata = ProcessingMetadata(
        ocr_time_ms=0.0,
        llm_time_ms=total_time_ms,
        total_time_ms=total_time_ms,
        ocr_confidence=1.0,
    )

    return ReceiptResponse(**receipt_data.dict(), processing_metadata=metadata)


@app.post("/parse")
async def parse_receipt(
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

    start_time = time.time()

    try:
        logger.info("Received /parse request")
        # Validate file type
        allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff"}
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{file.content_type}'. Accepted: JPEG, PNG, GIF, WebP, BMP, TIFF",
            )

        # Read image bytes
        image_bytes = await file.read()

        # Load image
        try:
            image = load_image_from_bytes(image_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

        # Try Gemini first if configured, falling back to PaddleOCR + Ollama on failure
        response = None
        if settings.parser_backend == "gemini" and gemini_service is not None:
            try:
                response = await _parse_with_gemini(image, extraction_options, start_time)
                logger.info("Receipt parsed using Gemini backend")
            except Exception as e:
                logger.warning(f"Gemini parsing failed, falling back to PaddleOCR + Ollama: {e}")

        if response is None:
            response = await _parse_with_paddleocr_ollama(image, extraction_options, start_time)
            if not isinstance(response, ReceiptResponse):
                # Error response (JSONResponse) from the fallback pipeline
                return response

        total_time_ms = (time.time() - start_time) * 1000

        # WORK-0002: keep a copy only when debugging locally (SAVE_OUTPUT=true).
        if settings.save_output:
            try:
                output_path = Path(settings.output_dir) / f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(output_path, "w") as f:
                    json.dump(response.dict(), f, indent=2)
                logger.info(f"Saved result to {output_path}")
            except Exception as e:
                logger.warning(f"Failed to save output: {e}")

        logger.info(
            f"Receipt parsed successfully in {total_time_ms:.0f}ms "
            f"(OCR: {response.processing_metadata.ocr_time_ms:.0f}ms, "
            f"LLM: {response.processing_metadata.llm_time_ms:.0f}ms)"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse-batch", response_model=BatchResponse)
async def parse_batch(
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

    start_time = time.time()

    # Validate batch size
    if len(files) > settings.batch_max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds maximum ({settings.batch_max_size})",
        )

    logger.info(f"Processing batch of {len(files)} receipts")

    results = []
    successful = 0
    failed = 0

    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff"}

    # Process each file
    for file in files:
        try:
            # Validate file type
            if file.content_type not in allowed_types:
                results.append(
                    BatchResult(
                        filename=file.filename,
                        success=False,
                        error=f"Unsupported file type '{file.content_type}'",
                    )
                )
                failed += 1
                continue

            # Read image bytes
            image_bytes = await file.read()

            # Load image
            try:
                image = load_image_from_bytes(image_bytes)
            except Exception as e:
                results.append(
                    BatchResult(
                        filename=file.filename,
                        success=False,
                        error=f"Invalid image: {str(e)}",
                    )
                )
                failed += 1
                continue

            # OCR extraction
            try:
                ocr_result = ocr_service.extract_text(image)
            except Exception as e:
                results.append(
                    BatchResult(
                        filename=file.filename,
                        success=False,
                        error=f"OCR failed: {str(e)}",
                    )
                )
                failed += 1
                continue

            # Check for text
            if not ocr_result.full_text.strip():
                results.append(
                    BatchResult(
                        filename=file.filename,
                        success=False,
                        error="No text detected",
                    )
                )
                failed += 1
                continue

            # LLM parsing
            try:
                receipt_data = await llm_service.parse_receipt(
                    ocr_result.full_text, extraction_options=extraction_options
                )
                results.append(
                    BatchResult(
                        filename=file.filename, success=True, data=receipt_data
                    )
                )
                successful += 1
            except Exception as e:
                results.append(
                    BatchResult(
                        filename=file.filename,
                        success=False,
                        error=f"LLM parsing failed: {str(e)}",
                    )
                )
                failed += 1

        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
            results.append(
                BatchResult(
                    filename=file.filename, success=False, error=f"Error: {str(e)}"
                )
            )
            failed += 1

    # Calculate total time
    processing_time_ms = (time.time() - start_time) * 1000

    logger.info(
        f"Batch processing completed in {processing_time_ms:.0f}ms "
        f"({successful} successful, {failed} failed)"
    )

    return BatchResponse(
        results=results,
        total=len(files),
        successful=successful,
        failed=failed,
        processing_time_ms=processing_time_ms,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
    )
