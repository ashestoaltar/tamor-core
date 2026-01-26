"""
Repair Service

Phase 8.2: Applies minimal repairs to flagged content.

Strategies:
- Anchor: Attach found evidence to claim
- Rewrite: Minimal sentence-level softening
- Clarify: Add clear thesis before hedges

Key principle: Never rewrite tone. Only fix specific issues.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from .linter import LintResult, LintIssue, LintSeverity
from .anchor_service import AnchorResult, Anchor


@dataclass
class RepairResult:
    """Result of repair attempt."""
    repaired: bool
    original_text: str
    repaired_text: str
    changes_made: List[str]
    anchors_attached: List[Anchor]


class RepairService:
    """
    Applies minimal repairs to flagged content.

    Rules:
    - Only modify flagged sentences, not entire response
    - Prefer attaching evidence over softening language
    - Never add generic hedges
    - Preserve author's voice
    """

    # Softening replacements (only for high-risk phrases)
    SOFTENINGS = {
        'this proves': 'this strongly suggests',
        'this definitively': 'this appears to',
        'this settles': 'this addresses',
        'this refutes': 'this challenges',
        'without question': 'with strong evidence',
        'beyond doubt': 'with high confidence',
        'the only interpretation': 'a compelling interpretation',
        'clearly teaches': 'appears to teach',
        'obviously means': 'likely means',
        'definitely': 'likely',
        'certainly': 'appears',
        'always': 'typically',
        'never': 'rarely',
        'must be': 'likely is',
        'cannot be': 'is unlikely to be',
    }

    def repair(
        self,
        text: str,
        lint_result: LintResult,
        anchor_result: Optional[AnchorResult] = None
    ) -> RepairResult:
        """
        Apply repairs to text based on lint results.

        Args:
            text: Original response text
            lint_result: Results from linting
            anchor_result: Optional anchor search results

        Returns:
            RepairResult with repaired text
        """
        if not lint_result.needs_repair:
            return RepairResult(
                repaired=False,
                original_text=text,
                repaired_text=text,
                changes_made=[],
                anchors_attached=[]
            )

        repaired_text = text
        changes_made = []
        anchors_attached = []

        strategy = lint_result.repair_strategy

        if strategy == 'anchor' and anchor_result and anchor_result.found:
            # Strategy A: Attach anchors
            repaired_text, anchor_changes = self._apply_anchor_strategy(
                repaired_text, lint_result, anchor_result
            )
            changes_made.extend(anchor_changes)
            anchors_attached = anchor_result.anchors

        elif strategy == 'rewrite':
            # Strategy B: Minimal sentence rewrite
            repaired_text, rewrite_changes = self._apply_rewrite_strategy(
                repaired_text, lint_result
            )
            changes_made.extend(rewrite_changes)

        elif strategy == 'clarify':
            # Strategy C: Clarify hedged content
            repaired_text, clarify_changes = self._apply_clarify_strategy(
                repaired_text, lint_result
            )
            changes_made.extend(clarify_changes)

        return RepairResult(
            repaired=len(changes_made) > 0,
            original_text=text,
            repaired_text=repaired_text,
            changes_made=changes_made,
            anchors_attached=anchors_attached
        )

    def _apply_anchor_strategy(
        self,
        text: str,
        lint_result: LintResult,
        anchor_result: AnchorResult
    ) -> tuple[str, List[str]]:
        """Attach anchors to support claims."""
        changes = []

        if not anchor_result.anchors:
            return text, changes

        # Find the first high-risk issue
        high_issues = [
            i for i in lint_result.issues
            if i.severity == LintSeverity.HIGH and i.category == 'certainty'
        ]

        if not high_issues:
            return text, changes

        # Format anchor citations
        anchor_text = self._format_anchors(anchor_result.anchors)

        # Insert after the problematic sentence
        issue = high_issues[0]
        sentence_end = text.find('.', issue.position[1])
        if sentence_end == -1:
            sentence_end = len(text)
        else:
            sentence_end += 1

        # Insert anchor reference
        repaired = text[:sentence_end] + anchor_text + text[sentence_end:]
        changes.append(f"Attached {len(anchor_result.anchors)} supporting reference(s)")

        return repaired, changes

    def _format_anchors(self, anchors: List[Anchor]) -> str:
        """Format anchors as inline citations."""
        if not anchors:
            return ""

        parts = []
        for anchor in anchors[:2]:  # Max 2 inline
            if anchor.verse:
                parts.append(f"[{anchor.verse}]")
            else:
                parts.append(f"[{anchor.source_name}]")

        return " " + ", ".join(parts)

    def _apply_rewrite_strategy(
        self,
        text: str,
        lint_result: LintResult
    ) -> tuple[str, List[str]]:
        """Apply minimal sentence-level softening."""
        changes = []
        repaired = text

        # Only fix high-severity certainty issues
        for issue in lint_result.issues:
            if issue.severity != LintSeverity.HIGH:
                continue
            if issue.category != 'certainty':
                continue

            # Find softening
            phrase_lower = issue.text_span.lower()
            for original, replacement in self.SOFTENINGS.items():
                if original in phrase_lower:
                    # Case-preserving replacement
                    pattern = re.compile(re.escape(original), re.IGNORECASE)

                    def replace_preserve_case(match):
                        orig = match.group(0)
                        if orig.isupper():
                            return replacement.upper()
                        elif orig[0].isupper():
                            return replacement.capitalize()
                        return replacement

                    new_text = pattern.sub(replace_preserve_case, repaired, count=1)
                    if new_text != repaired:
                        repaired = new_text
                        changes.append(f"Softened '{original}' → '{replacement}'")
                    break

        return repaired, changes

    def _apply_clarify_strategy(
        self,
        text: str,
        lint_result: LintResult
    ) -> tuple[str, List[str]]:
        """Add clarity to over-hedged content."""
        changes = []

        # Find clarity issues
        clarity_issues = [
            i for i in lint_result.issues
            if i.category == 'clarity'
        ]

        if not clarity_issues:
            return text, changes

        # For now, just flag - don't auto-insert thesis
        # A thesis must come from understanding the content
        changes.append("Flagged for manual clarity improvement")

        return text, changes


# Singleton
_repair_service = None

def get_repair_service() -> RepairService:
    """Get or create singleton repair service."""
    global _repair_service
    if _repair_service is None:
        _repair_service = RepairService()
    return _repair_service


def repair_response(
    text: str,
    lint_result: LintResult,
    anchor_result: Optional[AnchorResult] = None
) -> RepairResult:
    """Convenience function for repair."""
    return get_repair_service().repair(text, lint_result, anchor_result)
