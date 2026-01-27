"""
Global Hermeneutic Mode (GHM)

Phase 8.2.7: Epistemic honesty for Scripture-facing domains.
"""

from .config_loader import (
    load_ghm_rules,
    get_constraints,
    get_canonical_order,
    get_frameworks_requiring_disclosure,
    get_scripture_detection_patterns,
)
from .detector import (
    DetectionResult,
    GHMDetector,
    get_detector,
    detect_scripture_content,
)
from .enforcer import (
    FrameworkUsage,
    GHMViolation,
    EnforcementResult,
    GHMEnforcer,
    get_enforcer,
    enforce_ghm,
)

__all__ = [
    'load_ghm_rules',
    'get_constraints',
    'get_canonical_order',
    'get_frameworks_requiring_disclosure',
    'get_scripture_detection_patterns',
    'DetectionResult',
    'GHMDetector',
    'get_detector',
    'detect_scripture_content',
    'FrameworkUsage',
    'GHMViolation',
    'EnforcementResult',
    'GHMEnforcer',
    'get_enforcer',
    'enforce_ghm',
]
