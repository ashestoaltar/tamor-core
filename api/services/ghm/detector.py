"""
GHM Content Detector

Phase 8.2.7: Detects Scripture-facing content for fallback GHM activation.

This is SECONDARY to project-level declaration. It's conservative and suggestive,
not authoritative.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from .config_loader import get_scripture_detection_patterns


@dataclass
class DetectionResult:
    """Result of Scripture-facing content detection."""
    detected: bool
    confidence: float  # 0.0 to 1.0
    signals: List[str]  # What triggered detection
    suggested_action: str  # 'none', 'soft_ghm', 'suggest_ghm'


class GHMDetector:
    """
    Detects Scripture-facing content in text.

    Used for fallback detection in unassigned conversations.
    Conservative by design - better to miss than over-trigger.
    """

    def __init__(self):
        self._load_patterns()

    def _load_patterns(self):
        """Load detection patterns from config."""
        patterns = get_scripture_detection_patterns()

        self._book_names = set(
            name.lower() for name in patterns.get('book_names', [])
        )
        self._keywords = set(
            kw.lower() for kw in patterns.get('keywords', [])
        )
        self._regex_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in patterns.get('patterns', [])
        ]
        self._theological_markers = set(
            m.lower() for m in patterns.get('theological_markers', [])
        )

    def detect(self, text: str) -> DetectionResult:
        """
        Detect Scripture-facing content in text.

        Args:
            text: The text to analyze

        Returns:
            DetectionResult with detection info
        """
        signals = []
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))

        # Check for book names
        book_matches = words & self._book_names
        if book_matches:
            signals.append(f"Book names: {', '.join(book_matches)}")

        # Check for keywords
        keyword_matches = words & self._keywords
        if keyword_matches:
            signals.append(f"Keywords: {', '.join(keyword_matches)}")

        # Check regex patterns (verse references)
        for pattern in self._regex_patterns:
            matches = pattern.findall(text)
            if matches:
                signals.append(f"References: {', '.join(matches[:3])}")
                break  # One match is enough

        # Check theological markers (lower weight)
        marker_matches = words & self._theological_markers
        if marker_matches:
            signals.append(f"Theological terms: {', '.join(marker_matches)}")

        # Calculate confidence
        confidence = self._calculate_confidence(signals, book_matches, keyword_matches)

        # Determine action
        if confidence >= 0.7:
            suggested_action = 'suggest_ghm'
        elif confidence >= 0.4:
            suggested_action = 'soft_ghm'
        else:
            suggested_action = 'none'

        return DetectionResult(
            detected=confidence >= 0.3,
            confidence=confidence,
            signals=signals,
            suggested_action=suggested_action
        )

    def _calculate_confidence(
        self,
        signals: List[str],
        book_matches: set,
        keyword_matches: set
    ) -> float:
        """Calculate detection confidence."""
        if not signals:
            return 0.0

        score = 0.0

        # Book names are strong signal
        if book_matches:
            score += 0.4

        # Scripture keywords are strong
        if keyword_matches:
            score += 0.3

        # Verse references are very strong
        if any('References' in s for s in signals):
            score += 0.4

        # Theological markers add some weight
        if any('Theological' in s for s in signals):
            score += 0.2

        return min(score, 1.0)


# Singleton
_detector = None


def get_detector() -> GHMDetector:
    """Get or create singleton detector."""
    global _detector
    if _detector is None:
        _detector = GHMDetector()
    return _detector


def detect_scripture_content(text: str) -> DetectionResult:
    """Convenience function for detection."""
    return get_detector().detect(text)
