"""
GHM Enforcement Service

Phase 8.2.7: Enforces GHM constraints on LLM responses.

This runs AFTER the LLM generates a response, checking for violations
and applying corrections or disclosures.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .config_loader import (
    get_constraints,
    get_frameworks_requiring_disclosure,
    get_failure_conditions,
)


@dataclass
class FrameworkUsage:
    """A detected framework that requires disclosure."""
    framework_id: str
    framework_name: str
    origin: str
    matched_text: str


@dataclass
class GHMViolation:
    """A detected GHM constraint violation."""
    constraint_id: str
    constraint_name: str
    description: str
    violated_text: str
    severity: str  # 'warning', 'violation'


@dataclass
class EnforcementResult:
    """Result of GHM enforcement check."""
    passed: bool
    frameworks_used: List[FrameworkUsage] = field(default_factory=list)
    violations: List[GHMViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    disclosure_required: bool = False
    disclosure_text: Optional[str] = None


class GHMEnforcer:
    """
    Enforces GHM constraints on responses.

    Checks for:
    - Framework usage requiring disclosure (GHM-3)
    - Premature harmonization signals (GHM-4)
    - Comfort-softening language (GHM-5)
    - Absolute claims without warrant
    """

    # Patterns that suggest framework usage
    FRAMEWORK_PATTERNS = {
        'moral_ceremonial_civil': [
            r'moral law',
            r'ceremonial law',
            r'civil law',
            r'moral[,\s]+ceremonial[,\s]+(?:and\s+)?civil',
        ],
        'fulfilled_equals_ended': [
            r'fulfilled[,\s]+(?:and\s+)?(?:therefore\s+)?(?:ended|abolished|done away)',
            r'fulfilled\s+means?\s+(?:ended|abolished|finished)',
            r'fulfilled\s+in\s+Christ[,\s]+(?:so|therefore)',
        ],
        'covenant_of_works': [
            r'covenant of works',
            r'works\s+covenant',
        ],
        'dispensational_ages': [
            r'dispensation(?:al)?\s+(?:of|age)',
            r'age of (?:law|grace)',
            r'church age',
        ],
        'replacement_theology': [
            r'church\s+(?:replaces?|replaced)\s+Israel',
            r'new Israel',
            r'spiritual Israel',
        ],
        'law_gospel_antithesis': [
            r'law\s+(?:vs?\.?|versus|against)\s+gospel',
            r'antithesis\s+(?:of|between)\s+law\s+and\s+gospel',
        ],
    }

    # Patterns suggesting premature harmonization
    HARMONIZATION_PATTERNS = [
        r'(?:simply|obviously|clearly)\s+(?:means?|teaches?)',
        r'(?:all|most)\s+(?:scholars?|theologians?)\s+agree',
        r'the\s+(?:clear|obvious|plain)\s+(?:meaning|teaching)',
        r'(?:resolves?|solved?)\s+(?:the|this)\s+(?:tension|contradiction)',
    ]

    # Patterns suggesting comfort-softening
    SOFTENING_PATTERNS = [
        r'(?:but|however)[,\s]+(?:we|Christians?)\s+(?:today|now)',
        r'(?:of course|naturally)[,\s]+(?:this|that)\s+(?:doesn\'t|does not)\s+(?:mean|apply)',
        r'(?:we\s+)?(?:shouldn\'t|should not)\s+(?:take|read)\s+(?:this|that)\s+(?:too\s+)?literally',
    ]

    def __init__(self):
        self._compile_patterns()
        self._frameworks = {
            f['id']: f for f in get_frameworks_requiring_disclosure()
        }

    def _compile_patterns(self):
        """Compile regex patterns."""
        self._framework_re = {
            fid: [re.compile(p, re.IGNORECASE) for p in patterns]
            for fid, patterns in self.FRAMEWORK_PATTERNS.items()
        }
        self._harmonization_re = [
            re.compile(p, re.IGNORECASE) for p in self.HARMONIZATION_PATTERNS
        ]
        self._softening_re = [
            re.compile(p, re.IGNORECASE) for p in self.SOFTENING_PATTERNS
        ]

    def enforce(self, response_text: str, context: Dict[str, Any] = None) -> EnforcementResult:
        """
        Check response for GHM compliance.

        Args:
            response_text: The LLM response to check
            context: Optional context (query, project info, etc.)

        Returns:
            EnforcementResult with compliance info
        """
        context = context or {}

        frameworks_used = self._detect_frameworks(response_text)
        violations = []
        warnings = []

        # Check for harmonization (GHM-4)
        harmonization_matches = self._check_harmonization(response_text)
        if harmonization_matches:
            warnings.append(
                f"Possible premature harmonization detected: {harmonization_matches[0]}"
            )

        # Check for softening (GHM-5)
        softening_matches = self._check_softening(response_text)
        if softening_matches:
            warnings.append(
                f"Possible comfort-softening detected: {softening_matches[0]}"
            )

        # Determine if disclosure is required
        disclosure_required = len(frameworks_used) > 0
        disclosure_text = None

        if disclosure_required:
            disclosure_text = self._build_disclosure(frameworks_used)

        # Overall pass/fail
        passed = len(violations) == 0

        return EnforcementResult(
            passed=passed,
            frameworks_used=frameworks_used,
            violations=violations,
            warnings=warnings,
            disclosure_required=disclosure_required,
            disclosure_text=disclosure_text,
        )

    def _detect_frameworks(self, text: str) -> List[FrameworkUsage]:
        """Detect post-biblical frameworks in text."""
        found = []

        for framework_id, patterns in self._framework_re.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    framework_info = self._frameworks.get(framework_id, {})
                    found.append(FrameworkUsage(
                        framework_id=framework_id,
                        framework_name=framework_info.get('name', framework_id),
                        origin=framework_info.get('origin', 'Unknown'),
                        matched_text=match.group(0),
                    ))
                    break  # One match per framework is enough

        return found

    def _check_harmonization(self, text: str) -> List[str]:
        """Check for premature harmonization patterns."""
        matches = []
        for pattern in self._harmonization_re:
            match = pattern.search(text)
            if match:
                matches.append(match.group(0))
        return matches

    def _check_softening(self, text: str) -> List[str]:
        """Check for comfort-softening patterns."""
        matches = []
        for pattern in self._softening_re:
            match = pattern.search(text)
            if match:
                matches.append(match.group(0))
        return matches

    def _build_disclosure(self, frameworks: List[FrameworkUsage]) -> str:
        """Build disclosure text for frameworks used."""
        if not frameworks:
            return ""

        lines = ["**Frameworks used (post-biblical):**"]
        for fw in frameworks:
            lines.append(f"- {fw.framework_name} (origin: {fw.origin})")

        return "\n".join(lines)


# Singleton
_enforcer = None


def get_enforcer() -> GHMEnforcer:
    """Get or create singleton enforcer."""
    global _enforcer
    if _enforcer is None:
        _enforcer = GHMEnforcer()
    return _enforcer


def enforce_ghm(response_text: str, context: Dict[str, Any] = None) -> EnforcementResult:
    """Convenience function for enforcement."""
    return get_enforcer().enforce(response_text, context)
