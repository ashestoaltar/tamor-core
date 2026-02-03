#!/usr/bin/env python3
"""
LLM Provider Connectivity Test

Tests raw API connectivity to each configured LLM provider without requiring
Tamor services to be running.

Usage:
    python tests/test_llm_providers.py

Providers tested:
    - xAI (Grok) - Scholar mode provider
    - Anthropic (Claude) - Engineer mode provider
    - Ollama - Local classification/routing
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Tuple, Optional


# =============================================================================
# Configuration
# =============================================================================

TEST_MESSAGE = "What is 2 + 2? Reply with just the number."

# Provider endpoints
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
OLLAMA_DEFAULT_URL = "http://localhost:11434"

# Anthropic API version
ANTHROPIC_VERSION = "2023-06-01"


# =============================================================================
# Environment Loading
# =============================================================================

def load_env_file(env_path: str) -> dict:
    """Load environment variables from a .env file."""
    env_vars = {}
    if not os.path.exists(env_path):
        return env_vars

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def get_env(key: str, env_vars: dict, default: str = None) -> Optional[str]:
    """Get environment variable from loaded env or os.environ."""
    return env_vars.get(key) or os.environ.get(key) or default


# =============================================================================
# Provider Tests
# =============================================================================

def test_xai(api_key: str) -> Tuple[bool, str]:
    """
    Test xAI (Grok) API connectivity.

    Returns:
        (success: bool, message: str)
    """
    if not api_key:
        return False, "XAI_API_KEY not configured"

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "grok-4-fast-reasoning",  # Scholar mode default
            "messages": [
                {"role": "user", "content": TEST_MESSAGE}
            ],
            "max_tokens": 50,
        }

        response = requests.post(
            XAI_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            return False, "Empty response from xAI"

        # Check if response contains "4" (the answer to 2+2)
        if "4" in content:
            return True, f"Response: {content.strip()}"
        else:
            return True, f"Unexpected response: {content.strip()}"

    except requests.exceptions.Timeout:
        return False, "Request timed out"
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def test_anthropic(api_key: str) -> Tuple[bool, str]:
    """
    Test Anthropic (Claude) API connectivity.

    Note: Anthropic API format differs from OpenAI:
    - Uses x-api-key header (not Bearer token)
    - System prompt is a separate parameter (not in messages)
    - Response content is a list of blocks

    Returns:
        (success: bool, message: str)
    """
    if not api_key:
        return False, "ANTHROPIC_API_KEY not configured"

    try:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        payload = {
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 50,
            "messages": [
                {"role": "user", "content": TEST_MESSAGE}
            ],
        }

        response = requests.post(
            ANTHROPIC_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"

        data = response.json()

        # Anthropic returns content as a list of blocks
        content_blocks = data.get("content", [])
        content = "".join(
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        )

        if not content:
            return False, "Empty response from Anthropic"

        # Check if response contains "4"
        if "4" in content:
            return True, f"Response: {content.strip()}"
        else:
            return True, f"Unexpected response: {content.strip()}"

    except requests.exceptions.Timeout:
        return False, "Request timed out"
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def test_ollama(base_url: str, model: str = "phi3:mini") -> Tuple[bool, str]:
    """
    Test Ollama local LLM connectivity.

    Returns:
        (success: bool, message: str)
    """
    if not base_url:
        base_url = OLLAMA_DEFAULT_URL

    # First check if Ollama is running
    try:
        health_response = requests.get(f"{base_url}/api/tags", timeout=5)
        if health_response.status_code != 200:
            return False, f"Ollama not responding at {base_url}"

        # Check if the model is available
        models_data = health_response.json()
        available_models = [m.get("name", "") for m in models_data.get("models", [])]

        if not any(model in m for m in available_models):
            return False, f"Model '{model}' not found. Available: {', '.join(available_models[:5])}"

    except requests.exceptions.ConnectionError:
        return False, f"Ollama not running at {base_url}"
    except Exception as e:
        return False, f"Error checking Ollama: {e}"

    # Now test actual generation
    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": TEST_MESSAGE}
            ],
            "stream": False,
        }

        response = requests.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=120  # Ollama can be slow on CPU
        )

        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"

        data = response.json()
        content = data.get("message", {}).get("content", "")

        if not content:
            return False, "Empty response from Ollama"

        # Check if response contains "4"
        if "4" in content:
            return True, f"Response: {content.strip()[:100]}"
        else:
            return True, f"Unexpected response: {content.strip()[:100]}"

    except requests.exceptions.Timeout:
        return False, "Request timed out (Ollama may be slow on CPU)"
    except Exception as e:
        return False, f"Error: {e}"


# =============================================================================
# Main
# =============================================================================

def print_result(provider: str, success: bool, message: str):
    """Print formatted test result."""
    status = "\033[92m✓ PASS\033[0m" if success else "\033[91m✗ FAIL\033[0m"
    print(f"\n{provider}")
    print(f"  Status: {status}")
    print(f"  Detail: {message}")


def main():
    print("=" * 60)
    print("LLM Provider Connectivity Test")
    print("=" * 60)

    # Find and load .env file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    env_path = project_root / "api" / ".env"

    print(f"\nLoading config from: {env_path}")

    if not env_path.exists():
        print(f"\033[93mWarning: {env_path} not found, using environment variables\033[0m")
        env_vars = {}
    else:
        env_vars = load_env_file(str(env_path))
        print(f"Loaded {len(env_vars)} variables from .env")

    # Get credentials
    xai_key = get_env("XAI_API_KEY", env_vars)
    anthropic_key = get_env("ANTHROPIC_API_KEY", env_vars)
    ollama_url = get_env("OLLAMA_BASE_URL", env_vars, OLLAMA_DEFAULT_URL)
    ollama_model = get_env("OLLAMA_MODEL", env_vars, "phi3:mini")

    print(f"\nTest message: \"{TEST_MESSAGE}\"")
    print("-" * 60)

    results = []

    # Test xAI
    print("\nTesting xAI (Grok)...", end="", flush=True)
    success, message = test_xai(xai_key)
    results.append(("xAI (Grok)", success, message))
    print(" done")

    # Test Anthropic
    print("Testing Anthropic (Claude)...", end="", flush=True)
    success, message = test_anthropic(anthropic_key)
    results.append(("Anthropic (Claude)", success, message))
    print(" done")

    # Test Ollama
    print(f"Testing Ollama ({ollama_model})...", end="", flush=True)
    success, message = test_ollama(ollama_url, ollama_model)
    results.append((f"Ollama ({ollama_model})", success, message))
    print(" done")

    # Print results
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)

    passed = 0
    failed = 0
    for provider, success, message in results:
        print_result(provider, success, message)
        if success:
            passed += 1
        else:
            failed += 1

    # Summary
    print("\n" + "-" * 60)
    print(f"Summary: {passed} passed, {failed} failed")

    if failed > 0:
        print("\n\033[93mNote: Some providers failed. Check:")
        print("  - API keys in api/.env")
        print("  - Ollama running (ollama serve)")
        print("  - Network connectivity\033[0m")
        sys.exit(1)
    else:
        print("\n\033[92mAll providers operational!\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
