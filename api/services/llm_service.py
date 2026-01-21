# api/services/llm_service.py
"""
LLM Provider Abstraction Layer

This module provides a unified interface for LLM interactions,
enabling future multi-provider support (Phase 6.2).

Usage:
    from services.llm_service import get_llm_client, get_model_name

    client = get_llm_client()
    response = client.chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        model=get_model_name(),
    )
    print(response)  # The assistant's reply text
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

load_dotenv()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Send a chat completion request and return the assistant's response text.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier (provider-specific). Uses default if None.
            **kwargs: Additional provider-specific parameters.

        Returns:
            The assistant's response content as a string.
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this provider is properly configured."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider implementation."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        if not self.is_configured():
            raise RuntimeError("OpenAI API key not configured")

        client = self._get_client()
        model = model or get_model_name()

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )

        return completion.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Module-level singleton and helpers
# ---------------------------------------------------------------------------

_provider_instance: Optional[LLMProvider] = None


def get_llm_client() -> Optional[LLMProvider]:
    """
    Get the configured LLM provider instance.

    Returns None if no provider is configured.
    """
    global _provider_instance

    if _provider_instance is None:
        # Currently only OpenAI is supported
        # Future: check LLM_PROVIDER env var to select provider
        provider = OpenAIProvider()
        if provider.is_configured():
            _provider_instance = provider

    return _provider_instance


def get_model_name() -> str:
    """
    Get the configured model name.

    Returns the model identifier from environment or a sensible default.
    """
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def llm_is_configured() -> bool:
    """Check if an LLM provider is available and configured."""
    client = get_llm_client()
    return client is not None and client.is_configured()
