"""
Configuration management using pydantic-settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    # WORK-0008: local vision model in Ollama ("vlm_ollama" backend; falls back to paddleocr_ollama).
    vlm_host: str = "http://parser-ollama:11434"
    vlm_model: str = "qwen3.5:4b"
    vlm_timeout: int = 60
    vlm_max_side: int = 1280
    vlm_num_ctx: int = Field(default=8192, ge=1024)
    vlm_num_predict: int = Field(default=2048, ge=128)
    vlm_keep_alive: str = "30m"
    # Time kept for the local OCR fallback when the vision model fails or is slow.
    vlm_fallback_reserve_seconds: float = 10

    # Parser Backend Selection
    # "gemini": use Gemini vision API (falls back to paddleocr_ollama on failure)
    # "paddleocr_ollama": use PaddleOCR + Ollama only
    # "vlm_ollama": one local vision model (WORK-0008), falls back to paddleocr_ollama
    parser_backend: str = "paddleocr_ollama"

    # Gemini Configuration
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # WORK-0005: per-attempt HTTP timeout (seconds); Gemini is tried only while at least
    # fallback_reserve_seconds of the parse deadline remain for the local pipeline.
    gemini_timeout: int = 20
    fallback_reserve_seconds: float = 35

    # WORK-0005: the whole /parse request ends by this deadline (504). Innermost layer of
    # expense-api WORK-0073: parser 70 s < API 80 s < web 90 s < Cloudflare 100 s.
    parse_deadline_seconds: float = 70

    # OCR Configuration
    # requirements.txt installs the CPU Paddle wheel; GPU use must be explicit.
    ocr_use_gpu: bool = False
    ocr_lang: str = "en"
    ocr_use_angle_cls: bool = True

    # Ollama Configuration
    ollama_host: str = "http://shared-ollama:11434"
    ollama_model: str = "llama3.2-gpu:latest"
    ollama_timeout: int = 120
    ollama_temperature: float = 0.0
    ollama_top_p: float = 0.8
    ollama_num_predict: int = Field(default=2048, ge=128)
    ollama_num_ctx: int = Field(default=12288, ge=1024)
    # None lets Ollama place the text model automatically, independently of OCR.
    ollama_num_gpu: int | None = None
    ocr_device: str | None = None

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # Performance Settings
    batch_max_size: int = Field(default=10, ge=1, le=100)
    # Whole batch shares this budget; each receipt also gets parse_deadline_seconds.
    batch_deadline_seconds: float = Field(default=70, gt=0)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_request_bytes: int = Field(default=105 * 1024 * 1024, gt=0)
    max_image_pixels: int = Field(default=24_000_000, gt=0)
    ingress_timeout_seconds: float = Field(default=15, gt=0)
    health_timeout_seconds: float = Field(default=6, gt=0)
    max_active_parses: int = Field(default=1, ge=1)


    # Paths
    output_dir: str = "/app/output"
    # WORK-0002: parse results are not kept by default; true only for local debugging.
    save_output: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
