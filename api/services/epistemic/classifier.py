"""
Answer Classification Service

Phase 8.2: Classifies responses into four provenance tiers.

Tiers:
- DETERMINISTIC: Computed, exact, from trusted data
- GROUNDED_DIRECT: Restating or summarizing explicit text
- GROUNDED_CONTESTED: Grounded but interpretive, with live disagreement
- UNGROUNDED: No anchors, purely inferential
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .config_loader import (
    get_contested_markers,
    get_topic_contestation,
    get_risky_phrases
)


class AnswerType(Enum):
    """Four-tier answer classification."""
    DETERMINISTIC = "deterministic"
    GROUNDED_DIRECT = "grounded_direct"
    GROUNDED_CONTESTED = "grounded_contested"
    UNGROUNDED = "ungrounded"


class ContestationLevel(Enum):
    """Three-level contestation scale."""
    C1 = "intra_tradition"      # Nuance within same tradition
    C2 = "cross_tradition"      # Major traditions diverge
    C3 = "minority_position"    # Legitimate but not widely held


@dataclass
class ClassificationResult:
    """Result of answer classification."""
    answer_type: AnswerType
    confidence: float  # 0.0 to 1.0

    # Grounding info
    has_citations: bool = False
    citation_count: int = 0
    sources: List[str] = field(default_factory=list)

    # Contestation info (for GROUNDED_CONTESTED)
    is_contested: bool = False
    contested_domains: List[str] = field(default_factory=list)
    contestation_level: Optional[ContestationLevel] = None
    contestation_topic: Optional[str] = None
    alternative_positions: List[str] = field(default_factory=list)

    # Metadata
    classification_reason: str = ""


class AnswerClassifier:
    """
    Classifies LLM responses by provenance.

    Classification logic:
    1. Check for deterministic markers (counts, schedules, exact data)
    2. Check for citations/sources → grounded
    3. Check for contested domain markers → grounded_contested
    4. Default to ungrounded
    """

    # Patterns that indicate deterministic responses
    DETERMINISTIC_PATTERNS = [
        r'there (?:are|is) \d+',           # "there are 5 files"
        r'you have \d+',                    # "you have 3 tasks"
        r'(?:scheduled|set) for \d',        # "scheduled for 3:00"
        r'(?:reminder|task) (?:at|on) ',    # "reminder at 5pm"
        r'total[:\s]+\d+',                  # "total: 42"
        r'count[:\s]+\d+',                  # "count: 7"
        r'^\d+\s+(?:files?|items?|tasks?)', # "5 files found"
    ]

    # Patterns that indicate grounded responses
    GROUNDED_PATTERNS = [
        r'according to',
        r'the (?:text|passage|verse) (?:says|states)',
        r'in (?:verse|chapter) \d+',
        r'Paul (?:writes|says|states)',
        r'(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation) \d+[:\d]*',
        r'\[\d+\]',                         # Citation markers
        r'(?:source|citation|reference):',
    ]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self._deterministic_re = [
            re.compile(p, re.IGNORECASE) for p in self.DETERMINISTIC_PATTERNS
        ]
        self._grounded_re = [
            re.compile(p, re.IGNORECASE) for p in self.GROUNDED_PATTERNS
        ]

    def classify(
        self,
        response_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """
        Classify a response by provenance.

        Args:
            response_text: The LLM response text
            context: Optional context (citations, query type, etc.)

        Returns:
            ClassificationResult with tier and metadata
        """
        context = context or {}

        # Check deterministic first
        if self._is_deterministic(response_text, context):
            return ClassificationResult(
                answer_type=AnswerType.DETERMINISTIC,
                confidence=1.0,
                classification_reason="Response contains computed/exact data"
            )

        # Check for grounding
        is_grounded, sources = self._check_grounding(response_text, context)

        if is_grounded:
            # Check if contested
            contested_result = self._check_contestation(response_text)

            if contested_result['is_contested']:
                return ClassificationResult(
                    answer_type=AnswerType.GROUNDED_CONTESTED,
                    confidence=0.85,
                    has_citations=True,
                    citation_count=len(sources),
                    sources=sources,
                    is_contested=True,
                    contested_domains=contested_result['domains'],
                    contestation_level=contested_result.get('level'),
                    contestation_topic=contested_result.get('topic'),
                    alternative_positions=contested_result.get('alternatives', []),
                    classification_reason="Response is grounded but addresses contested topic"
                )
            else:
                return ClassificationResult(
                    answer_type=AnswerType.GROUNDED_DIRECT,
                    confidence=0.9,
                    has_citations=True,
                    citation_count=len(sources),
                    sources=sources,
                    classification_reason="Response directly references source material"
                )

        # Default: ungrounded
        return ClassificationResult(
            answer_type=AnswerType.UNGROUNDED,
            confidence=0.7,
            classification_reason="Response is inferential without direct grounding"
        )

    def _is_deterministic(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> bool:
        """Check if response is deterministic."""
        # Context override
        if context.get('is_deterministic'):
            return True

        # Query type check
        query_type = context.get('query_type', '')
        if query_type in ('count', 'list', 'schedule', 'status'):
            return True

        # Pattern matching
        for pattern in self._deterministic_re:
            if pattern.search(text):
                return True

        return False

    def _check_grounding(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """Check if response is grounded in sources."""
        sources = []

        # Context-provided sources
        if context.get('sources'):
            sources.extend(context['sources'])

        # Pattern matching
        for pattern in self._grounded_re:
            matches = pattern.findall(text)
            if matches:
                sources.extend(matches[:5])  # Limit

        # Scripture reference detection
        scripture_refs = self._find_scripture_refs(text)
        sources.extend(scripture_refs)

        return len(sources) > 0, list(set(sources))

    def _find_scripture_refs(self, text: str) -> List[str]:
        """Find scripture references in text."""
        # Simple pattern for book + chapter(:verse)
        pattern = r'\b(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalm|Proverbs|Ecclesiastes|Song|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation)\s+\d+(?::\d+(?:-\d+)?)?'

        matches = re.findall(pattern, text, re.IGNORECASE)
        return matches[:10]  # Limit

    def _check_contestation(self, text: str) -> Dict[str, Any]:
        """Check if response addresses contested topics."""
        result = {
            'is_contested': False,
            'domains': [],
            'level': None,
            'topic': None,
            'alternatives': []
        }

        text_lower = text.lower()

        # Check domain markers
        all_markers = get_contested_markers()
        for domain, markers in all_markers.items():
            for marker in markers:
                if marker.lower() in text_lower:
                    result['is_contested'] = True
                    if domain not in result['domains']:
                        result['domains'].append(domain)

        # Check manual topic mappings
        for domain_markers in all_markers.values():
            for marker in domain_markers:
                if marker.lower() in text_lower:
                    topic_info = get_topic_contestation(marker)
                    if topic_info:
                        result['is_contested'] = True
                        result['topic'] = marker

                        level_str = topic_info.get('level', 'C2')
                        if level_str == 'C1':
                            result['level'] = ContestationLevel.C1
                        elif level_str == 'C3':
                            result['level'] = ContestationLevel.C3
                        else:
                            result['level'] = ContestationLevel.C2

                        result['alternatives'] = topic_info.get('positions', [])
                        break

        # Default level if contested but no specific mapping
        if result['is_contested'] and not result['level']:
            result['level'] = ContestationLevel.C2

        return result


# Singleton instance
_classifier = None


def get_classifier() -> AnswerClassifier:
    """Get or create singleton classifier."""
    global _classifier
    if _classifier is None:
        _classifier = AnswerClassifier()
    return _classifier


def classify_answer(
    response_text: str,
    context: Optional[Dict[str, Any]] = None
) -> ClassificationResult:
    """Convenience function for classification."""
    return get_classifier().classify(response_text, context)
