"""App configuration."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings."""

    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./logs.db")

    # OpenRouter for /insights — one API for 300+ models: https://openrouter.ai/settings/keys
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

    # OpenAI for /insights (optional fallback)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Google AI (Gemini) for /insights — fallback; free tier at aistudio.google.com
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Validation
    max_log_size_bytes: int = int(os.getenv("MAX_LOG_SIZE_BYTES", "50000"))
    allowed_levels: tuple = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


settings = Settings()
