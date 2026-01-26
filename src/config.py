"""
Configuration management using pydantic-settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    # OCR Configuration
    ocr_use_gpu: bool = True
    ocr_lang: str = "en"
    ocr_use_angle_cls: bool = True

    # Ollama Configuration
    ollama_host: str = "http://shared-ollama:11434"
    ollama_model: str = "llama3.2-gpu:latest"
    ollama_timeout: int = 120
    ollama_temperature: float = 0.0
    ollama_top_p: float = 0.8
    ollama_num_predict: int = 1024

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # Performance Settings
    batch_max_size: int = 10

    # Paths
    output_dir: str = "/app/output"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
