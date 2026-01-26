"""
Epistemic Pipeline

Phase 8.2: Main orchestration for the epistemic honesty system.

Pipeline flow:
1. Classify answer type
2. Lint for issues
3. Attempt anchoring (if needed)
4. Apply repairs (if needed)
5. Return enhanced response with metadata
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from .classifier import (
    AnswerType,
    ContestationLevel,
    ClassificationResult,
    classify_answer
)
from .linter import LintResult, lint_response
from .anchor_service import AnchorResult, find_anchors, set_session_context
from .repair_service import RepairResult, repair_response


@dataclass
class EpistemicMetadata:
    """Metadata attached to response for UI."""
    answer_type: str
    badge: str  # "deterministic", "grounded", "contested"

    # Contestation (if applicable)
    is_contested: bool = False
    contestation_level: Optional[str] = None  # "C1", "C2", "C3"
    contested_domains: List[str] = field(default_factory=list)
    alternative_positions: List[str] = field(default_factory=list)

    # Sources (if grounded)
    has_sources: bool = False
    sources: List[str] = field(default_factory=list)

    # Lint summary
    had_issues: bool = False
    was_repaired: bool = False
    certainty_score: float = 0.0
    clarity_score: float = 1.0


@dataclass
class EpistemicResult:
    """Complete result from epistemic pipeline."""
    original_text: str
    processed_text: str
    metadata: EpistemicMetadata

    # Detailed results (for debugging/logging)
    classification: ClassificationResult
    lint_result: LintResult
    anchor_result: Optional[AnchorResult] = None
    repair_result: Optional[RepairResult] = None


class EpistemicPipeline:
    """
    Main pipeline for epistemic processing.

    Usage:
        pipeline = EpistemicPipeline()
        pipeline.set_context(session_context)
        result = pipeline.process(response_text)

        # Use result.processed_text for display
        # Use result.metadata for UI badges
    """

    def __init__(self):
        self._context: Dict[str, Any] = {}

    def set_context(self, context: Dict[str, Any]):
        """Set session context (retrieved sources, query type, etc.)."""
        self._context = context
        set_session_context(context)

    def process(
        self,
        response_text: str,
        skip_repair: bool = False
    ) -> EpistemicResult:
        """
        Process a response through the epistemic pipeline.

        Args:
            response_text: The LLM response to process
            skip_repair: If True, classify and lint but don't repair

        Returns:
            EpistemicResult with processed text and metadata
        """
        # Step 1: Classify
        classification = classify_answer(response_text, self._context)

        # Step 2: Lint
        lint_result = lint_response(response_text, classification)

        # Step 3: Anchor (if needed)
        anchor_result = None
        if lint_result.needs_repair and lint_result.repair_strategy == 'anchor':
            # Extract claim from first high-risk issue
            high_issues = [
                i for i in lint_result.issues
                if i.category == 'certainty'
            ]
            if high_issues:
                claim = high_issues[0].text_span
                deep = self._context.get('user_prefers_accuracy', False)
                anchor_result = find_anchors(claim, deep_search=deep)

        # Step 4: Repair (if needed and not skipped)
        repair_result = None
        processed_text = response_text

        if lint_result.needs_repair and not skip_repair:
            repair_result = repair_response(
                response_text, lint_result, anchor_result
            )
            if repair_result.repaired:
                processed_text = repair_result.repaired_text

        # Step 5: Build metadata
        metadata = self._build_metadata(
            classification, lint_result, repair_result
        )

        return EpistemicResult(
            original_text=response_text,
            processed_text=processed_text,
            metadata=metadata,
            classification=classification,
            lint_result=lint_result,
            anchor_result=anchor_result,
            repair_result=repair_result
        )

    def _build_metadata(
        self,
        classification: ClassificationResult,
        lint_result: LintResult,
        repair_result: Optional[RepairResult]
    ) -> EpistemicMetadata:
        """Build UI metadata from results."""
        # Determine badge
        if classification.answer_type == AnswerType.DETERMINISTIC:
            badge = "deterministic"
        elif classification.answer_type == AnswerType.GROUNDED_CONTESTED:
            badge = "contested"
        elif classification.answer_type == AnswerType.GROUNDED_DIRECT:
            badge = "grounded"
        else:
            badge = "grounded"  # Don't expose "ungrounded" - just no badge

        # Contestation level string
        contestation_level = None
        if classification.contestation_level:
            level_map = {
                ContestationLevel.C1: "C1",
                ContestationLevel.C2: "C2",
                ContestationLevel.C3: "C3"
            }
            contestation_level = level_map.get(classification.contestation_level)

        return EpistemicMetadata(
            answer_type=classification.answer_type.value,
            badge=badge,
            is_contested=classification.is_contested,
            contestation_level=contestation_level,
            contested_domains=classification.contested_domains,
            alternative_positions=classification.alternative_positions,
            has_sources=classification.has_citations,
            sources=classification.sources[:5],  # Limit for UI
            had_issues=lint_result.has_issues,
            was_repaired=repair_result.repaired if repair_result else False,
            certainty_score=lint_result.certainty_score,
            clarity_score=lint_result.clarity_score
        )


# Singleton
_pipeline = None

def get_pipeline() -> EpistemicPipeline:
    """Get or create singleton pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = EpistemicPipeline()
    return _pipeline


def process_response(
    response_text: str,
    context: Optional[Dict[str, Any]] = None,
    skip_repair: bool = False
) -> EpistemicResult:
    """
    Convenience function for processing a response.

    Args:
        response_text: The LLM response
        context: Optional session context
        skip_repair: If True, only classify and lint

    Returns:
        EpistemicResult with processed text and metadata
    """
    pipeline = get_pipeline()
    if context:
        pipeline.set_context(context)
    return pipeline.process(response_text, skip_repair)
