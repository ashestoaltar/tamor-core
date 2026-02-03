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
from .frame_analyzer import (
    FrameAssumption,
    FrameAnalyzer,
    get_frame_analyzer,
    analyze_question_frames,
    should_challenge_frame,
)
from .prompt_builder import (
    build_ghm_system_prompt,
    build_ghm_user_prefix,
    load_hermeneutic_config,
    get_research_directives_prompt,
)
from .profile_loader import (
    load_profile,
    get_available_profiles,
    get_profile_prompt_addition,
    is_valid_profile,
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
    'FrameAssumption',
    'FrameAnalyzer',
    'get_frame_analyzer',
    'analyze_question_frames',
    'should_challenge_frame',
    'build_ghm_system_prompt',
    'build_ghm_user_prefix',
    'load_hermeneutic_config',
    'get_research_directives_prompt',
    'load_profile',
    'get_available_profiles',
    'get_profile_prompt_addition',
    'is_valid_profile',
]
