"""
OCR Service using PaddleOCR for text extraction from receipt images.
"""

import logging
import time
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

from src.models import OCRResult
from src.config import settings

logger = logging.getLogger(__name__)


class ReceiptOCRService:
    """
    OCR service for extracting text from receipt images using PaddleOCR.

    Uses PaddleOCR's built-in text detection and recognition which already
    returns text in reading order (top-to-bottom, left-to-right).
    """

    def __init__(self, use_gpu: bool = None):
        """
        Initialize PaddleOCR with optimized configuration for receipts.

        Args:
            use_gpu: Enable GPU acceleration (defaults to settings.ocr_use_gpu)
        """
        use_gpu = use_gpu if use_gpu is not None else settings.ocr_use_gpu

        logger.info(f"Initializing PaddleOCR (GPU: {use_gpu})")

        # Optimized PaddleOCR configuration for receipts
        # Disable preprocessing steps that aren't needed for typical receipt images
        self.ocr = PaddleOCR(
            lang=settings.ocr_lang,
            use_doc_orientation_classify=False,  # Receipts are usually upright
            use_doc_unwarping=False,  # Skip document unwarping
            use_textline_orientation=False,  # Skip textline orientation detection
        )

        # Create output directory
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("PaddleOCR initialized successfully")

    def extract_text(self, image: Image.Image) -> OCRResult:
        """
        Extract text from a single image.

        Args:
            image: PIL Image object

        Returns:
            OCRResult with extracted text, confidence, and boxes
        """
        start_time = time.time()

        try:
            # Ensure RGB format and convert to numpy array
            if image.mode != "RGB":
                image = image.convert("RGB")
            img_array = np.array(image)

            # Run OCR - PaddleOCR returns results in reading order
            results = list(self.ocr.predict(img_array))

            # Handle empty results
            if not results:
                logger.info("No text detected in image")
                return OCRResult(full_text="", confidence=0.0, boxes=[])

            # Access result directly (OCRResult object behaves like a dict)
            ocr_result = results[0]
            rec_texts = ocr_result.get("rec_texts", [])
            rec_scores = ocr_result.get("rec_scores", [])
            dt_polys = ocr_result.get("dt_polys")

            # PaddleOCR returns text in reading order - just join with newlines
            full_text = "\n".join(rec_texts) if rec_texts else ""

            # Calculate average confidence
            confidence = float(np.mean(rec_scores)) if rec_scores else 0.0

            # Convert boxes to serializable format (for API response)
            boxes = self._serialize_boxes(dt_polys, rec_texts, rec_scores)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"OCR completed in {elapsed_ms:.0f}ms (confidence: {confidence:.2f})"
            )

            return OCRResult(
                full_text=full_text,
                confidence=confidence,
                boxes=boxes,
            )

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}", exc_info=True)
            raise RuntimeError(f"OCR extraction failed: {str(e)}")

    def extract_batch(self, images: List[Image.Image]) -> List[OCRResult]:
        """
        Extract text from multiple images sequentially.

        Args:
            images: List of PIL Image objects

        Returns:
            List of OCRResult objects
        """
        logger.info(f"Starting batch OCR for {len(images)} images")
        start_time = time.time()

        # Process sequentially (PaddleOCR handles internal parallelism)
        results = [self.extract_text(img) for img in images]

        elapsed_ms = (time.time() - start_time) * 1000
        avg_time = elapsed_ms / len(images) if images else 0

        logger.info(
            f"Batch OCR completed in {elapsed_ms:.0f}ms ({avg_time:.0f}ms per image)"
        )

        return results

    async def health_check(self) -> dict:
        """
        Check OCR service health.

        Returns:
            Health status dictionary
        """
        try:
            status = "ready" if self.ocr is not None else "not_ready"
            return {
                "status": status,
                "backend": "PaddleOCR PP-OCRv4",
                "gpu_enabled": settings.ocr_use_gpu,
                "language": settings.ocr_lang,
            }
        except Exception as e:
            logger.error(f"OCR health check failed: {e}")
            return {"status": "error", "error": str(e)}

    @staticmethod
    def _serialize_boxes(dt_polys, rec_texts, rec_scores) -> list:
        """
        Convert boxes to JSON-serializable format.

        Args:
            dt_polys: Detection polygons (numpy array)
            rec_texts: Recognized texts (list)
            rec_scores: Recognition scores (numpy array)

        Returns:
            List of serializable box dictionaries
        """
        if dt_polys is None or not len(rec_texts):
            return []

        # Convert numpy arrays to Python types efficiently
        # dt_polys shape is (N, 4, 2) where N is number of boxes
        polys_list = dt_polys.astype(float).tolist() if hasattr(dt_polys, 'tolist') else dt_polys
        scores_list = rec_scores.tolist() if hasattr(rec_scores, 'tolist') else list(rec_scores)

        return [
            {"points": polys_list[i], "text": rec_texts[i], "confidence": scores_list[i]}
            for i in range(len(rec_texts))
        ]
