# api/services/llm_service.py
"""
LLM Provider Abstraction Layer

This module provides a unified interface for LLM interactions,
supporting multiple providers (OpenAI, Ollama) with routing capabilities.

Usage:
    from services.llm_service import get_llm_client, get_model_name

    # Default provider (OpenAI)
    client = get_llm_client()
    response = client.chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        model=get_model_name(),
    )

    # Local LLM (Ollama)
    local = get_local_llm_client()
    if local:
        response = local.chat_completion(
            messages=[{"role": "user", "content": "Summarize this"}],
        )
"""

import os
import requests
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


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider implementation."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._default_model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self._available = None  # Cache availability check

    def is_configured(self) -> bool:
        """Check if Ollama is running and accessible."""
        if self._available is not None:
            return self._available

        try:
            response = requests.get(f"{self._base_url}/api/tags", timeout=2)
            self._available = response.status_code == 200
        except requests.RequestException:
            self._available = False

        return self._available

    def list_models(self) -> List[str]:
        """List available models in Ollama."""
        try:
            response = requests.get(f"{self._base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except requests.RequestException:
            pass
        return []

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Send a chat completion request to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model name (e.g., 'llama3.1:8b', 'mistral'). Uses default if None.
            **kwargs: Additional parameters (temperature, etc.)

        Returns:
            The assistant's response content as a string.
        """
        if not self.is_configured():
            raise RuntimeError("Ollama is not running or not accessible")

        model = model or self._default_model

        # Ollama uses /api/chat for chat completions
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        # Pass through supported kwargs
        if "temperature" in kwargs:
            payload["options"] = payload.get("options", {})
            payload["options"]["temperature"] = kwargs["temperature"]

        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=300,  # 5 min timeout for slow CPU inference
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Simple text generation (non-chat format).

        Useful for summarization, extraction, and other single-turn tasks.
        """
        if not self.is_configured():
            raise RuntimeError("Ollama is not running or not accessible")

        model = model or self._default_model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        if "temperature" in kwargs:
            payload["options"] = payload.get("options", {})
            payload["options"]["temperature"] = kwargs["temperature"]

        try:
            response = requests.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")


# ---------------------------------------------------------------------------
# Module-level singletons and helpers
# ---------------------------------------------------------------------------

_openai_instance: Optional[OpenAIProvider] = None
_ollama_instance: Optional[OllamaProvider] = None


def get_llm_client() -> Optional[LLMProvider]:
    """
    Get the primary (cloud) LLM provider instance.

    Returns OpenAI provider if configured, None otherwise.
    """
    global _openai_instance

    if _openai_instance is None:
        provider = OpenAIProvider()
        if provider.is_configured():
            _openai_instance = provider

    return _openai_instance


def get_local_llm_client() -> Optional[OllamaProvider]:
    """
    Get the local LLM provider instance (Ollama).

    Returns OllamaProvider if Ollama is running, None otherwise.
    """
    global _ollama_instance

    if _ollama_instance is None:
        provider = OllamaProvider()
        if provider.is_configured():
            _ollama_instance = provider

    return _ollama_instance


def get_model_name() -> str:
    """
    Get the configured cloud model name.

    Returns the model identifier from environment or a sensible default.
    """
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def get_local_model_name() -> str:
    """
    Get the configured local model name.

    Returns the Ollama model from environment or default.
    """
    return os.getenv("OLLAMA_MODEL", "llama3.1:8b")


def llm_is_configured() -> bool:
    """Check if the primary LLM provider is available and configured."""
    client = get_llm_client()
    return client is not None and client.is_configured()


def local_llm_is_configured() -> bool:
    """Check if the local LLM (Ollama) is available."""
    client = get_local_llm_client()
    return client is not None and client.is_configured()


def get_best_available_client(prefer_local: bool = False) -> Optional[LLMProvider]:
    """
    Get the best available LLM client.

    Args:
        prefer_local: If True, prefer Ollama over cloud providers.

    Returns:
        The best available provider, or None if none configured.
    """
    if prefer_local:
        local = get_local_llm_client()
        if local:
            return local
        return get_llm_client()
    else:
        cloud = get_llm_client()
        if cloud:
            return cloud
        return get_local_llm_client()
