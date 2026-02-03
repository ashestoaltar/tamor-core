# api/services/llm_service.py
"""
LLM Provider Abstraction Layer

This module provides a unified interface for LLM interactions,
supporting multiple providers (xAI, Anthropic, OpenAI, Ollama) with routing capabilities.

Provider Architecture:
    - xAI (Grok): Scholar mode — theological research, textual analysis
    - Anthropic (Claude): Engineer mode — coding tasks, instruction-following
    - Ollama: Classification/routing — local, zero-cost
    - OpenAI: Legacy/fallback (retained for compatibility)

Usage:
    from services.llm_service import (
        get_xai_client, get_anthropic_client, get_local_llm_client
    )

    # xAI for Scholar mode (theological research)
    xai = get_xai_client()
    if xai:
        response = xai.chat_completion(
            messages=[{"role": "user", "content": "Analyze Acts 15..."}],
        )

    # Anthropic for Engineer mode (coding tasks)
    claude = get_anthropic_client()
    if claude:
        response = claude.chat_completion(
            messages=[
                {"role": "system", "content": "You are a coding assistant."},
                {"role": "user", "content": "Write a Python function..."},
            ],
        )

    # Local LLM for classification (Ollama)
    local = get_local_llm_client()
    if local:
        response = local.chat_completion(
            messages=[{"role": "user", "content": "Classify this intent..."}],
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


class XAIProvider(LLMProvider):
    """
    xAI (Grok) API provider implementation.

    Used for Scholar mode — theological research, textual analysis.
    API is OpenAI-compatible format.
    """

    XAI_API_URL = "https://api.x.ai/v1/chat/completions"
    DEFAULT_MODEL = "grok-4-fast-reasoning"
    DEFAULT_TIMEOUT = 120  # seconds

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("XAI_API_KEY")

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Send a chat completion request to xAI (Grok).

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model name (default: grok-4-fast-reasoning).
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            The assistant's response content as a string.
        """
        if not self.is_configured():
            raise RuntimeError("xAI API key not configured (XAI_API_KEY)")

        model = model or self.DEFAULT_MODEL

        # Build request payload (OpenAI-compatible format)
        payload = {
            "model": model,
            "messages": messages,
        }

        # Pass through supported kwargs
        for key in ("temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"):
            if key in kwargs:
                payload[key] = kwargs[key]

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        timeout = kwargs.get("timeout", self.DEFAULT_TIMEOUT)

        try:
            response = requests.post(
                self.XAI_API_URL,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            # Parse response (OpenAI-compatible format)
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("xAI returned no choices in response")

            return choices[0].get("message", {}).get("content", "")

        except requests.Timeout:
            raise RuntimeError(f"xAI request timed out after {timeout}s")
        except requests.HTTPError as e:
            # Extract error details if available
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(e))
            except Exception:
                error_msg = str(e)
            raise RuntimeError(f"xAI API error: {error_msg}")
        except requests.RequestException as e:
            raise RuntimeError(f"xAI request failed: {e}")


class AnthropicProvider(LLMProvider):
    """
    Anthropic (Claude) API provider implementation.

    Used for Engineer mode — coding tasks, instruction-following.
    Note: Anthropic API has a different format than OpenAI:
    - System prompt goes in top-level "system" parameter, not in messages
    - Messages array only contains user/assistant roles
    - Response content is a list of blocks, not a string
    """

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    ANTHROPIC_VERSION = "2023-06-01"
    DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
    DEFAULT_TIMEOUT = 120  # seconds
    DEFAULT_MAX_TOKENS = 4096

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Send a chat completion request to Anthropic (Claude).

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                      System messages are extracted and sent separately.
            model: Model name (default: claude-sonnet-4-5-20250929).
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            The assistant's response content as a string.
        """
        if not self.is_configured():
            raise RuntimeError("Anthropic API key not configured (ANTHROPIC_API_KEY)")

        model = model or self.DEFAULT_MODEL

        # Separate system messages from user/assistant messages
        # Anthropic requires system prompt in a separate top-level parameter
        system_prompt = None
        filtered_messages = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                # Concatenate multiple system messages if present
                if system_prompt is None:
                    system_prompt = content
                else:
                    system_prompt = f"{system_prompt}\n\n{content}"
            elif role in ("user", "assistant"):
                filtered_messages.append({"role": role, "content": content})

        # Build request payload
        payload = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": kwargs.get("max_tokens", self.DEFAULT_MAX_TOKENS),
        }

        # Add system prompt if present
        if system_prompt:
            payload["system"] = system_prompt

        # Pass through supported kwargs
        for key in ("temperature", "top_p", "top_k", "stop_sequences"):
            if key in kwargs:
                payload[key] = kwargs[key]

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        timeout = kwargs.get("timeout", self.DEFAULT_TIMEOUT)

        try:
            response = requests.post(
                self.ANTHROPIC_API_URL,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            # Parse response — content is a LIST of blocks
            content_blocks = data.get("content", [])
            if not content_blocks:
                raise RuntimeError("Anthropic returned no content in response")

            # Extract text from all text blocks
            text_parts = [
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "text"
            ]

            return "".join(text_parts)

        except requests.Timeout:
            raise RuntimeError(f"Anthropic request timed out after {timeout}s")
        except requests.HTTPError as e:
            # Extract error details if available
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(e))
            except Exception:
                error_msg = str(e)
            raise RuntimeError(f"Anthropic API error: {error_msg}")
        except requests.RequestException as e:
            raise RuntimeError(f"Anthropic request failed: {e}")


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
_xai_instance: Optional[XAIProvider] = None
_anthropic_instance: Optional[AnthropicProvider] = None
_ollama_instance: Optional[OllamaProvider] = None


def get_xai_client() -> Optional[XAIProvider]:
    """
    Get the xAI (Grok) provider instance.

    Used for Scholar mode — theological research, textual analysis.
    Returns XAIProvider if configured, None otherwise.
    """
    global _xai_instance

    if _xai_instance is None:
        provider = XAIProvider()
        if provider.is_configured():
            _xai_instance = provider

    return _xai_instance


def xai_is_configured() -> bool:
    """Check if xAI (Grok) is configured."""
    client = get_xai_client()
    return client is not None and client.is_configured()


def get_anthropic_client() -> Optional[AnthropicProvider]:
    """
    Get the Anthropic (Claude) provider instance.

    Used for Engineer mode — coding tasks, instruction-following.
    Returns AnthropicProvider if configured, None otherwise.
    """
    global _anthropic_instance

    if _anthropic_instance is None:
        provider = AnthropicProvider()
        if provider.is_configured():
            _anthropic_instance = provider

    return _anthropic_instance


def anthropic_is_configured() -> bool:
    """Check if Anthropic (Claude) is configured."""
    client = get_anthropic_client()
    return client is not None and client.is_configured()


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


# ---------------------------------------------------------------------------
# Mode-based provider routing
# ---------------------------------------------------------------------------

# Cache for modes config
_modes_config: Optional[Dict[str, Any]] = None


def _load_modes_config() -> Dict[str, Any]:
    """Load modes configuration from config/modes.json."""
    global _modes_config

    if _modes_config is not None:
        return _modes_config

    import json
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "config" / "modes.json"

    try:
        with open(config_path) as f:
            _modes_config = json.load(f)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to load modes.json: {e}")
        _modes_config = {}

    return _modes_config


# Agent-to-provider mapping
# Maps agent types to their preferred cloud provider
AGENT_PROVIDER_MAP = {
    "researcher": "xai",      # Theological research → Grok
    "writer": "xai",          # Theological writing → Grok
    "engineer": "anthropic",  # Coding tasks → Claude
    "archivist": "anthropic", # Memory commands → Claude (instruction-following)
}


def get_provider_for_mode(mode: str) -> Optional[LLMProvider]:
    """
    Get the cloud LLM provider configured for a specific mode.

    Args:
        mode: Mode name (e.g., "Scholar", "Forge")

    Returns:
        The configured provider, or None if not found/configured.
    """
    modes = _load_modes_config()
    mode_config = modes.get(mode, {})

    provider_name = mode_config.get("provider", "").lower()

    if provider_name == "xai":
        return get_xai_client()
    elif provider_name == "anthropic":
        return get_anthropic_client()
    elif provider_name == "openai":
        return get_llm_client()

    # Default fallback
    return None


def get_model_for_mode(mode: str) -> Optional[str]:
    """
    Get the model name configured for a specific mode.

    Args:
        mode: Mode name (e.g., "Scholar", "Forge")

    Returns:
        The configured model name, or None if not specified.
    """
    modes = _load_modes_config()
    mode_config = modes.get(mode, {})
    return mode_config.get("model")


def get_provider_for_agent(agent_type: str) -> Optional[LLMProvider]:
    """
    Get the cloud LLM provider for a specific agent type.

    Args:
        agent_type: Agent type (e.g., "researcher", "writer", "engineer", "archivist")

    Returns:
        The appropriate provider for this agent type, or fallback if not configured.
    """
    provider_name = AGENT_PROVIDER_MAP.get(agent_type.lower(), "xai")

    if provider_name == "xai":
        client = get_xai_client()
        if client:
            return client
    elif provider_name == "anthropic":
        client = get_anthropic_client()
        if client:
            return client

    # Fallback chain: try xAI → Anthropic → OpenAI
    for getter in [get_xai_client, get_anthropic_client, get_llm_client]:
        client = getter()
        if client and client.is_configured():
            return client

    return None


def get_model_for_agent(agent_type: str) -> str:
    """
    Get the default model name for a specific agent type.

    Args:
        agent_type: Agent type (e.g., "researcher", "writer", "engineer", "archivist")

    Returns:
        The appropriate model name for this agent type.
    """
    provider_name = AGENT_PROVIDER_MAP.get(agent_type.lower(), "xai")

    if provider_name == "xai":
        return XAIProvider.DEFAULT_MODEL
    elif provider_name == "anthropic":
        return AnthropicProvider.DEFAULT_MODEL

    return get_model_name()  # OpenAI default
