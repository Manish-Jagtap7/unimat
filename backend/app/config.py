"""
UniMat AI — Application Configuration

Loads settings from environment variables via pydantic-settings.
"""

from urllib.parse import quote_plus
from pydantic_settings import BaseSettings
from pydantic import computed_field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # ─── Database (separate fields to handle special chars in password) ──────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "unimat"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """Build the SQLAlchemy connection URL with properly escaped password."""
        password = quote_plus(self.DB_PASSWORD)
        return f"postgresql+psycopg2://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ─── Gemini API ─────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""

    # ─── ChromaDB ───────────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # ─── Embedding Model ───────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"

    # ─── Server ─────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ─── Classification Thresholds ──────────────────────────────────────────────
    DUPLICATE_THRESHOLD: float = 0.95
    NEAR_DUPLICATE_THRESHOLD: float = 0.85

    # ─── LLM Batching ──────────────────────────────────────────────────────────
    LLM_BATCH_SIZE: int = 15
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ─── Upload ─────────────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
