"""
GHM Rules Configuration Loader

Phase 8.2.7: Loads GHM rules from YAML config.
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from functools import lru_cache

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'config',
    'ghm_rules.yml'
)


@lru_cache(maxsize=1)
def load_ghm_rules() -> Dict[str, Any]:
    """Load GHM rules from YAML config."""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"GHM rules not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def reload_ghm_rules():
    """Clear cache and reload rules."""
    load_ghm_rules.cache_clear()
    return load_ghm_rules()


def get_constraints() -> Dict[str, Dict[str, Any]]:
    """Get the five GHM constraints."""
    rules = load_ghm_rules()
    return rules.get('constraints', {})


def get_canonical_order() -> List[Dict[str, Any]]:
    """Get canonical authority order."""
    rules = load_ghm_rules()
    return rules.get('canonical_order', [])


def get_frameworks_requiring_disclosure() -> List[Dict[str, Any]]:
    """Get list of frameworks that must be disclosed."""
    rules = load_ghm_rules()
    return rules.get('frameworks_requiring_disclosure', [])


def get_scripture_detection_patterns() -> Dict[str, Any]:
    """Get patterns for Scripture-facing content detection."""
    rules = load_ghm_rules()
    return rules.get('scripture_detection', {})


def get_output_requirements(mode: str = 'when_ghm_active') -> List[str]:
    """Get output requirements for a GHM mode."""
    rules = load_ghm_rules()
    requirements = rules.get('output_requirements', {})
    return requirements.get(mode, [])


def get_failure_conditions() -> List[str]:
    """Get GHM failure conditions."""
    rules = load_ghm_rules()
    return rules.get('failure_conditions', [])
