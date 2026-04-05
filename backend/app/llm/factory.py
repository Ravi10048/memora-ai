from __future__ import annotations

from app.config import LLMProvider, settings
from app.exceptions import LLMProviderError
from app.llm.base import BaseLLMProvider
from app.llm.groq_provider import GroqProvider
from app.llm.ollama_provider import OllamaProvider

_provider_instance: BaseLLMProvider | None = None


def get_llm_provider(provider: LLMProvider | None = None) -> BaseLLMProvider:
    global _provider_instance

    target = provider or settings.llm_provider

    if _provider_instance and _provider_instance.provider_name == target.value:
        return _provider_instance

    if target == LLMProvider.GROQ:
        _provider_instance = GroqProvider()
    elif target == LLMProvider.OLLAMA:
        _provider_instance = OllamaProvider()
    else:
        raise LLMProviderError(f"Unknown LLM provider: {target}")

    return _provider_instance


def reset_provider() -> None:
    global _provider_instance
    _provider_instance = None
