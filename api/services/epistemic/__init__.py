"""
Epistemic Honesty System

Phase 8.2: Truth signaling for Tamor responses.

Main entry point: process_response()

Example:
    from services.epistemic import process_response

    result = process_response(
        response_text="This proves that election is corporate...",
        context={'query_type': 'theological'}
    )

    print(result.metadata.badge)  # "contested"
    print(result.processed_text)  # May be repaired
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

from .anchor_service import (
    Anchor,
    AnchorResult,
    AnchorService,
    get_anchor_service,
    find_anchors,
    set_session_context
)

from .repair_service import (
    RepairResult,
    RepairService,
    get_repair_service,
    repair_response
)

from .pipeline import (
    EpistemicMetadata,
    EpistemicResult,
    EpistemicPipeline,
    get_pipeline,
    process_response
)

__all__ = [
    # Config
    'load_rules',
    'reload_rules',
    'get_risky_phrases',
    'get_contested_markers',
    'get_topic_contestation',

    # Classification
    'AnswerType',
    'ContestationLevel',
    'ClassificationResult',
    'classify_answer',

    # Linting
    'LintSeverity',
    'LintIssue',
    'LintResult',
    'lint_response',

    # Anchoring
    'Anchor',
    'AnchorResult',
    'find_anchors',
    'set_session_context',

    # Repair
    'RepairResult',
    'repair_response',

    # Pipeline (main entry)
    'EpistemicMetadata',
    'EpistemicResult',
    'process_response',
]
