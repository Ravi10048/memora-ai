from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings as app_settings
from app.llm.factory import get_llm_provider

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingsResponse(BaseModel):
    llm_provider: str
    groq_model: str
    ollama_model: str
    short_term_max_messages: int
    long_term_min_relevance: float
    long_term_recency_weight: float
    entity_confidence_threshold: float


@router.get("", response_model=SettingsResponse)
def get_settings():
    return SettingsResponse(
        llm_provider=app_settings.llm_provider.value,
        groq_model=app_settings.groq_model,
        ollama_model=app_settings.ollama_model,
        short_term_max_messages=app_settings.short_term_max_messages,
        long_term_min_relevance=app_settings.long_term_min_relevance,
        long_term_recency_weight=app_settings.long_term_recency_weight,
        entity_confidence_threshold=app_settings.entity_confidence_threshold,
    )


@router.get("/health")
async def health_check():
    try:
        provider = get_llm_provider()
        is_healthy = await provider.health_check()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "provider": provider.provider_name,
            "model": provider.model_name,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
