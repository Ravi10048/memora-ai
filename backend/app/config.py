from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class LLMProvider(str, Enum):
    GROQ = "groq"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM Provider ──
    llm_provider: LLMProvider = LLMProvider.GROQ

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # ── Memory Settings ──
    short_term_max_messages: int = 20
    long_term_min_relevance: float = 0.75
    long_term_recency_weight: float = 0.3
    entity_confidence_threshold: float = 0.7

    # ── Server ──
    host: str = "0.0.0.0"
    port: int = 8090
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'agent.db'}"
    chroma_persist_dir: str = str(PROJECT_ROOT / "chroma_data")
    log_level: str = "INFO"


settings = Settings()
