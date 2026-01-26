"""
Epistemic Rules Configuration Loader

Phase 8.2: Loads and provides access to epistemic rules.
"""

import os
import re
import yaml
from typing import Dict, List, Any, Optional
from functools import lru_cache


CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'config',
    'epistemic_rules.yml'
)


@lru_cache(maxsize=1)
def load_rules() -> Dict[str, Any]:
    """Load epistemic rules from YAML config."""
    if not os.path.exists(CONFIG_PATH):
        return get_default_rules()

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_default_rules() -> Dict[str, Any]:
    """Return minimal default rules if config file missing."""
    return {
        'version': '1.0',
        'risky_phrases': {
            'high_risk': ['this proves', 'definitely', 'without question'],
            'medium_risk': ['certainly', 'always', 'never']
        },
        'contested_markers': {},
        'topic_contestation': {},
        'allowed_absolutes': [],
        'hedge_tokens': ['maybe', 'possibly', 'perhaps', 'might', 'could'],
        'max_hedges_per_sentence': 2,
        'anchor_settings': {
            'fast_budget_ms': 250,
            'deep_budget_ms': 800,
            'sources': ['session_context', 'library_cache']
        }
    }


def reload_rules():
    """Clear cache and reload rules."""
    load_rules.cache_clear()
    return load_rules()


def get_risky_phrases(level: str = 'all') -> List[str]:
    """Get risky phrases by risk level."""
    rules = load_rules()
    phrases = rules.get('risky_phrases', {})

    if level == 'high':
        return phrases.get('high_risk', [])
    elif level == 'medium':
        return phrases.get('medium_risk', [])
    else:
        return phrases.get('high_risk', []) + phrases.get('medium_risk', [])


def get_contested_markers(domain: str = None) -> Dict[str, List[str]]:
    """Get contested domain markers, optionally filtered by domain."""
    rules = load_rules()
    markers = rules.get('contested_markers', {})

    if domain:
        return {domain: markers.get(domain, [])}
    return markers


def get_topic_contestation(topic: str) -> Optional[Dict[str, Any]]:
    """Get manual contestation mapping for a specific topic."""
    rules = load_rules()
    topics = rules.get('topic_contestation', {})

    # Exact match
    if topic in topics:
        return topics[topic]

    # Partial match
    topic_lower = topic.lower()
    for key, value in topics.items():
        if key.lower() in topic_lower or topic_lower in key.lower():
            return value

    return None


def get_hedge_tokens() -> List[str]:
    """Get list of hedge tokens."""
    rules = load_rules()
    return rules.get('hedge_tokens', [])


def get_max_hedges() -> int:
    """Get max allowed hedges per sentence."""
    rules = load_rules()
    return rules.get('max_hedges_per_sentence', 2)


def get_anchor_settings() -> Dict[str, Any]:
    """Get anchor search settings."""
    rules = load_rules()
    return rules.get('anchor_settings', {})


def is_allowed_absolute(text: str) -> bool:
    """Check if text matches an allowed absolute pattern."""
    rules = load_rules()
    allowed = rules.get('allowed_absolutes', [])

    for entry in allowed:
        pattern = entry.get('pattern', '')
        if pattern and re.search(pattern, text, re.IGNORECASE):
            return True

    return False
