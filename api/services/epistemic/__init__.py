"""
Epistemic Honesty System

Phase 8.2: Truth signaling for Tamor responses.
"""

from .config_loader import (
    load_rules,
    reload_rules,
    get_risky_phrases,
    get_contested_markers,
    get_topic_contestation,
    get_hedge_tokens,
    get_max_hedges,
    get_anchor_settings,
    is_allowed_absolute
)

from .classifier import (
    AnswerType,
    ContestationLevel,
    ClassificationResult,
    AnswerClassifier,
    get_classifier,
    classify_answer
)

from .linter import (
    LintSeverity,
    LintIssue,
    LintResult,
    ConfidenceLinter,
    get_linter,
    lint_response
)

__all__ = [
    # Config loader
    'load_rules',
    'reload_rules',
    'get_risky_phrases',
    'get_contested_markers',
    'get_topic_contestation',
    'get_hedge_tokens',
    'get_max_hedges',
    'get_anchor_settings',
    'is_allowed_absolute',
    # Classifier
    'AnswerType',
    'ContestationLevel',
    'ClassificationResult',
    'AnswerClassifier',
    'get_classifier',
    'classify_answer',
    # Linter
    'LintSeverity',
    'LintIssue',
    'LintResult',
    'ConfidenceLinter',
    'get_linter',
    'lint_response'
]
