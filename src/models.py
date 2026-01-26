"""
Pydantic models for receipt parsing API.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ExtractionOptions(BaseModel):
    """Options to control which fields the LLM should extract."""

    items: bool = Field(default=True, description="Extract line items")
    date: bool = Field(default=True, description="Extract transaction date")
    time: bool = Field(default=True, description="Extract transaction time")
    subtotal: bool = Field(default=True, description="Extract subtotal")
    tax: bool = Field(default=True, description="Extract tax amount")
    tip: bool = Field(default=False, description="Extract tip amount")
    discount: bool = Field(default=False, description="Extract discount amount")
    payment_method: bool = Field(default=False, description="Extract payment method")
    merchant_address: bool = Field(default=False, description="Extract merchant address")
    merchant_phone: bool = Field(default=False, description="Extract merchant phone")
    receipt_number: bool = Field(default=False, description="Extract receipt/transaction number")
    cashier: bool = Field(default=False, description="Extract cashier name")


class ReceiptItem(BaseModel):
    """Individual line item on a receipt."""

    name: str = Field(..., description="Item name or description")
    quantity: Optional[int] = Field(default=1, ge=1, description="Quantity purchased")
    unit_price: Optional[float] = Field(default=None, description="Price per unit")
    total_price: float = Field(..., description="Total price for this line item")

    def __init__(self, **data):
        # Handle null quantity by defaulting to 1
        if data.get('quantity') is None:
            data['quantity'] = 1
        super().__init__(**data)


class ReceiptData(BaseModel):
    """Complete receipt data structure matching existing API."""

    merchant_name: str = Field(..., description="Store or restaurant name")
    merchant_address: Optional[str] = Field(default=None, description="Full merchant address")
    merchant_phone: Optional[str] = Field(default=None, description="Phone number (e.g., +01234567890)")

    date: Optional[str] = Field(default=None, description="Transaction date in YYYY-MM-DD format")
    time: Optional[str] = Field(default=None, description="Transaction time in HH:MM format")

    items: List[ReceiptItem] = Field(default_factory=list, description="List of purchased items")

    subtotal: Optional[float] = Field(default=None, description="Subtotal before tax")
    tax: Optional[float] = Field(default=None, description="Tax amount")
    tip: Optional[float] = Field(default=None, description="Tip amount")
    discount: Optional[float] = Field(default=None, description="Discount amount")
    total: float = Field(..., description="Total amount paid")

    payment_method: Optional[str] = Field(default=None, description="Payment method (cash/card/etc)")
    card_last_4: Optional[str] = Field(default=None, description="Last 4 digits of card if visible")
    receipt_number: Optional[str] = Field(default=None, description="Transaction/receipt number")
    cashier: Optional[str] = Field(default=None, description="Cashier name if visible")


class ProcessingMetadata(BaseModel):
    """Metadata about the processing pipeline."""

    ocr_time_ms: float = Field(..., description="OCR processing time in milliseconds")
    llm_time_ms: float = Field(..., description="LLM processing time in milliseconds")
    total_time_ms: float = Field(..., description="Total processing time in milliseconds")
    ocr_confidence: float = Field(..., ge=0.0, le=1.0, description="Average OCR confidence score")


class ReceiptResponse(BaseModel):
    """API response for single receipt parsing."""

    # Receipt data fields (flattened)
    merchant_name: str
    merchant_address: Optional[str] = None
    merchant_phone: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    items: List[ReceiptItem]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    tip: Optional[float] = None
    discount: Optional[float] = None
    total: float
    payment_method: Optional[str] = None
    card_last_4: Optional[str] = None
    receipt_number: Optional[str] = None
    cashier: Optional[str] = None

    # Processing metadata
    processing_metadata: ProcessingMetadata


class OCRResult(BaseModel):
    """Result from OCR extraction."""

    full_text: str = Field(..., description="Complete extracted text, spatially organized")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Average confidence score")
    boxes: List[dict] = Field(default_factory=list, description="Individual text boxes with positions")


class ParseError(BaseModel):
    """Error response for failed parsing."""

    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(default=None, description="Additional error details")
    ocr_text: Optional[str] = Field(default=None, description="Raw OCR text if available")
    ocr_confidence: Optional[float] = Field(default=None, description="OCR confidence if available")


class BatchResult(BaseModel):
    """Result for a single receipt in batch processing."""

    filename: str
    success: bool
    data: Optional[ReceiptData] = None
    error: Optional[str] = None


class BatchResponse(BaseModel):
    """API response for batch receipt parsing."""

    results: List[BatchResult]
    total: int
    successful: int
    failed: int
    processing_time_ms: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    services: dict
    timestamp: str


class ServiceInfo(BaseModel):
    """Basic service information."""

    name: str = "Receipt Parser API"
    version: str = "1.0.0"
    description: str = "Two-stage receipt parser using PaddleOCR + Ollama"
    architecture: str = "PaddleOCR (OCR) → Ollama (LLM) → JSON"
