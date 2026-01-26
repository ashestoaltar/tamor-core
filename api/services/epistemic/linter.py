"""
Confidence Linting Service

Phase 8.2: Detects and flags overconfident language.

Two lint dimensions:
1. Certainty posture vs provenance (absolutist claims need backing)
2. Clarity erosion (too many hedges = evasion)
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum

from .config_loader import (
    get_risky_phrases,
    get_hedge_tokens,
    get_max_hedges,
    is_allowed_absolute
)
from .classifier import AnswerType, ClassificationResult


class LintSeverity(Enum):
    """Severity of lint issue."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class LintIssue:
    """A single lint issue found in text."""
    severity: LintSeverity
    category: str  # "certainty" or "clarity"
    message: str
    text_span: str  # The problematic text
    position: Tuple[int, int]  # Start, end positions
    suggestion: Optional[str] = None


@dataclass
class LintResult:
    """Result of linting a response."""
    has_issues: bool
    issues: List[LintIssue] = field(default_factory=list)
    certainty_score: float = 0.0  # 0 = appropriately uncertain, 1 = overconfident
    clarity_score: float = 1.0    # 1 = clear, 0 = hedged into oblivion
    needs_repair: bool = False
    repair_strategy: Optional[str] = None  # "anchor", "rewrite", "clarify"


class ConfidenceLinter:
    """
    Lints LLM responses for epistemic issues.

    Rules:
    - High-risk phrases require deterministic backing or grounded citation
    - Medium-risk phrases get flagged but not blocked
    - Too many hedges in one sentence = clarity erosion
    - Hedges without a clear thesis = evasion
    """

    def __init__(self):
        self._load_patterns()

    def _load_patterns(self):
        """Load patterns from config."""
        self._high_risk = [
            re.compile(re.escape(p), re.IGNORECASE)
            for p in get_risky_phrases('high')
        ]
        self._medium_risk = [
            re.compile(re.escape(p), re.IGNORECASE)
            for p in get_risky_phrases('medium')
        ]
        self._hedge_tokens = get_hedge_tokens()
        self._max_hedges = get_max_hedges()

    def lint(
        self,
        response_text: str,
        classification: ClassificationResult
    ) -> LintResult:
        """
        Lint a response for epistemic issues.

        Args:
            response_text: The response to lint
            classification: The answer classification result

        Returns:
            LintResult with issues and repair recommendations
        """
        issues = []

        # Check certainty
        certainty_issues = self._check_certainty(response_text, classification)
        issues.extend(certainty_issues)

        # Check clarity
        clarity_issues = self._check_clarity(response_text)
        issues.extend(clarity_issues)

        # Calculate scores
        certainty_score = self._calculate_certainty_score(certainty_issues)
        clarity_score = self._calculate_clarity_score(clarity_issues, response_text)

        # Determine if repair needed
        needs_repair = any(i.severity == LintSeverity.HIGH for i in issues)
        repair_strategy = self._determine_repair_strategy(
            issues, classification
        ) if needs_repair else None

        return LintResult(
            has_issues=len(issues) > 0,
            issues=issues,
            certainty_score=certainty_score,
            clarity_score=clarity_score,
            needs_repair=needs_repair,
            repair_strategy=repair_strategy
        )

    def _check_certainty(
        self,
        text: str,
        classification: ClassificationResult
    ) -> List[LintIssue]:
        """Check for overconfident certainty claims."""
        issues = []

        # High-risk phrases
        for pattern in self._high_risk:
            for match in pattern.finditer(text):
                # Check if it's an allowed absolute
                sentence = self._get_sentence(text, match.start())
                if is_allowed_absolute(sentence):
                    continue

                # Check if grounded
                if classification.answer_type in (
                    AnswerType.DETERMINISTIC,
                    AnswerType.GROUNDED_DIRECT
                ):
                    # Grounded = allowed
                    continue

                issues.append(LintIssue(
                    severity=LintSeverity.HIGH,
                    category="certainty",
                    message=f"Absolutist claim '{match.group()}' without grounding",
                    text_span=match.group(),
                    position=(match.start(), match.end()),
                    suggestion="Attach citation or soften claim"
                ))

        # Medium-risk phrases (only flag if ungrounded)
        if classification.answer_type == AnswerType.UNGROUNDED:
            for pattern in self._medium_risk:
                for match in pattern.finditer(text):
                    sentence = self._get_sentence(text, match.start())
                    if is_allowed_absolute(sentence):
                        continue

                    issues.append(LintIssue(
                        severity=LintSeverity.MEDIUM,
                        category="certainty",
                        message=f"Strong claim '{match.group()}' in ungrounded response",
                        text_span=match.group(),
                        position=(match.start(), match.end()),
                        suggestion="Consider softening or adding source"
                    ))

        return issues

    def _check_clarity(self, text: str) -> List[LintIssue]:
        """Check for clarity erosion (too many hedges)."""
        issues = []

        sentences = self._split_sentences(text)

        for sentence in sentences:
            hedge_count = sum(
                1 for token in self._hedge_tokens
                if token.lower() in sentence.lower()
            )

            if hedge_count > self._max_hedges:
                # Find position in original text
                pos = text.find(sentence)

                issues.append(LintIssue(
                    severity=LintSeverity.MEDIUM,
                    category="clarity",
                    message=f"Sentence has {hedge_count} hedge tokens (max: {self._max_hedges})",
                    text_span=sentence[:50] + "..." if len(sentence) > 50 else sentence,
                    position=(pos, pos + len(sentence)),
                    suggestion="State thesis clearly, then qualify"
                ))

        return issues

    def _get_sentence(self, text: str, position: int) -> str:
        """Extract the sentence containing a position."""
        # Find sentence boundaries
        start = text.rfind('.', 0, position)
        start = start + 1 if start != -1 else 0

        end = text.find('.', position)
        end = end + 1 if end != -1 else len(text)

        return text[start:end].strip()

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _calculate_certainty_score(self, issues: List[LintIssue]) -> float:
        """Calculate certainty score (higher = more overconfident)."""
        if not issues:
            return 0.0

        certainty_issues = [i for i in issues if i.category == "certainty"]
        if not certainty_issues:
            return 0.0

        high_count = sum(1 for i in certainty_issues if i.severity == LintSeverity.HIGH)
        medium_count = sum(1 for i in certainty_issues if i.severity == LintSeverity.MEDIUM)

        # Score formula: high issues weight more
        score = (high_count * 0.3) + (medium_count * 0.1)
        return min(score, 1.0)

    def _calculate_clarity_score(
        self,
        issues: List[LintIssue],
        text: str
    ) -> float:
        """Calculate clarity score (higher = clearer)."""
        clarity_issues = [i for i in issues if i.category == "clarity"]

        if not clarity_issues:
            return 1.0

        sentence_count = len(self._split_sentences(text))
        if sentence_count == 0:
            return 1.0

        # Ratio of problematic sentences
        problem_ratio = len(clarity_issues) / sentence_count
        return max(0.0, 1.0 - problem_ratio)

    def _determine_repair_strategy(
        self,
        issues: List[LintIssue],
        classification: ClassificationResult
    ) -> str:
        """Determine best repair strategy."""
        certainty_issues = [i for i in issues if i.category == "certainty"]
        clarity_issues = [i for i in issues if i.category == "clarity"]

        # If ungrounded with certainty issues, try to anchor
        if classification.answer_type == AnswerType.UNGROUNDED and certainty_issues:
            return "anchor"

        # If grounded_contested with high certainty issues, rewrite
        if classification.answer_type == AnswerType.GROUNDED_CONTESTED:
            return "rewrite"

        # If clarity issues dominate
        if len(clarity_issues) > len(certainty_issues):
            return "clarify"

        # Default
        return "rewrite"


# Singleton
_linter = None


def get_linter() -> ConfidenceLinter:
    """Get or create singleton linter."""
    global _linter
    if _linter is None:
        _linter = ConfidenceLinter()
    return _linter


def lint_response(
    response_text: str,
    classification: ClassificationResult
) -> LintResult:
    """Convenience function for linting."""
    return get_linter().lint(response_text, classification)
