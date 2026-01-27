"""
GHM Frame Analyzer

Detects when questions assume post-biblical frameworks.
When detected under GHM, the frame must be challenged before answering.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .config_loader import get_frameworks_requiring_disclosure


@dataclass
class FrameAssumption:
    """A detected framework assumption in a question."""
    framework_id: str
    framework_name: str
    origin: str
    trigger_phrase: str
    challenge_prompt: str


# Framework assumption patterns and their challenges
FRAME_PATTERNS = {
    'moral_ceremonial_civil': {
        'patterns': [
            r'moral\s+law',
            r'ceremonial\s+law',
            r'civil\s+law',
            r'moral[,\s]+ceremonial',
            r'ceremonial[,\s]+(?:vs?\.?|versus|or)\s+moral',
            r'which\s+laws?\s+(?:are|is)\s+(?:still\s+)?(?:binding|valid)',
            r'(?:is|are)\s+(?:the\s+)?(?:dietary|food|sabbath)\s+(?:laws?|rules?)\s+(?:moral|ceremonial)',
        ],
        'challenge': (
            "This question assumes a distinction between 'moral' and 'ceremonial' law "
            "that Scripture itself doesn't make. The Torah doesn't categorize commands this way — "
            "that framework developed in medieval scholasticism.\n\n"
            "Let's examine what the biblical texts actually say:"
        ),
    },
    'fulfilled_equals_ended': {
        'patterns': [
            r'fulfilled\s+(?:means?|=|equals?)\s+(?:ended|abolished|done)',
            r'(?:did|does|has)\s+(?:jesus|christ)\s+(?:end|abolish|fulfill)',
            r'law\s+(?:was\s+)?fulfilled\s+(?:so|therefore|and)',
            r'fulfilled\s+(?:and\s+)?(?:therefore\s+)?(?:no\s+longer|not\s+)',
            r'since\s+(?:christ|jesus)\s+fulfilled',
        ],
        'challenge': (
            "This question assumes 'fulfilled' means 'ended' — but that equivalence isn't "
            "established in the text. In Matthew 5:17, Jesus explicitly denies coming to abolish, "
            "using 'fulfill' in contrast to 'destroy.'\n\n"
            "Let's look at how the texts actually use these terms:"
        ),
    },
    'under_law_vs_grace': {
        'patterns': [
            r'under\s+(?:the\s+)?law\s+(?:or|vs?\.?|versus)\s+(?:under\s+)?grace',
            r'(?:are\s+)?(?:we|christians?)\s+(?:still\s+)?under\s+(?:the\s+)?law',
            r'grace\s+(?:replaced|replaces|vs?\.?|versus)\s+(?:the\s+)?law',
            r'law\s+(?:or|vs?\.?|versus)\s+grace',
            r'not\s+under\s+law\s+but\s+under\s+grace',
        ],
        'challenge': (
            "This framing assumes 'under law' and 'under grace' are opposites — but Paul's "
            "usage is more specific. In context, 'under law' often refers to the law's condemning "
            "function for those seeking justification by works, not to Torah observance itself.\n\n"
            "Let's examine how Paul actually uses these phrases:"
        ),
    },
    'old_new_covenant_replacement': {
        'patterns': [
            r'new\s+covenant\s+(?:replaced?|replaces?|superseded?)',
            r'old\s+covenant\s+(?:ended|obsolete|replaced)',
            r'(?:did|does)\s+(?:the\s+)?new\s+covenant\s+(?:replace|end|abolish)',
            r'(?:are\s+)?(?:we|christians?)\s+(?:under|in)\s+(?:the\s+)?new\s+covenant\s+(?:not|instead)',
        ],
        'challenge': (
            "This question assumes the New Covenant *replaces* rather than *renews*. But Jeremiah 31 "
            "describes the New Covenant as writing the *same Torah* on hearts — internalization, not "
            "replacement.\n\n"
            "Let's look at the covenant texts directly:"
        ),
    },
    'works_of_law': {
        'patterns': [
            r'works\s+of\s+(?:the\s+)?law\s+(?:means?|=|refers?\s+to)\s+(?:torah|obedience|keeping)',
            r'(?:paul|scripture)\s+(?:condemns?|rejects?)\s+(?:keeping|obeying)\s+(?:the\s+)?law',
            r'justified\s+by\s+(?:faith|grace)\s+not\s+(?:by\s+)?(?:works|law)',
        ],
        'challenge': (
            "This framing may conflate 'works of the law' with Torah obedience generally. Recent "
            "scholarship suggests Paul's phrase refers specifically to Jewish identity markers "
            "(circumcision, dietary laws, calendar) as covenant boundary conditions — not to "
            "faithful obedience itself.\n\n"
            "Let's examine Paul's actual usage:"
        ),
    },
    'sabbath_ceremonial': {
        'patterns': [
            r'(?:is|was)\s+(?:the\s+)?sabbath\s+(?:ceremonial|moral)',
            r'sabbath\s+(?:ended|abolished|fulfilled|transferred)',
            r'(?:do|should)\s+(?:we|christians?)\s+(?:keep|observe)\s+(?:the\s+)?sabbath',
        ],
        'challenge': (
            "This question assumes we can categorize Sabbath as 'ceremonial' or 'moral' — but "
            "that framework isn't biblical. The Sabbath is grounded in creation (Genesis 2) and "
            "the Decalogue (Exodus 20), yet involves specific practices.\n\n"
            "Let's look at what Scripture says about Sabbath directly:"
        ),
    },
}


class FrameAnalyzer:
    """
    Analyzes questions for framework assumptions.

    When GHM is active, detected frameworks must be challenged
    before answering within them.
    """

    def __init__(self):
        self._compile_patterns()
        self._frameworks = {
            f['id']: f for f in get_frameworks_requiring_disclosure()
        }

    def _compile_patterns(self):
        """Compile regex patterns."""
        self._frame_re = {}
        for frame_id, frame_data in FRAME_PATTERNS.items():
            self._frame_re[frame_id] = [
                re.compile(p, re.IGNORECASE)
                for p in frame_data['patterns']
            ]

    def analyze(self, question: str) -> List[FrameAssumption]:
        """
        Analyze a question for framework assumptions.

        Args:
            question: The user's question

        Returns:
            List of detected framework assumptions
        """
        assumptions = []

        for frame_id, patterns in self._frame_re.items():
            for pattern in patterns:
                match = pattern.search(question)
                if match:
                    frame_info = self._frameworks.get(frame_id, {})
                    frame_data = FRAME_PATTERNS.get(frame_id, {})

                    assumptions.append(FrameAssumption(
                        framework_id=frame_id,
                        framework_name=frame_info.get('name', frame_id),
                        origin=frame_info.get('origin', 'Post-biblical'),
                        trigger_phrase=match.group(0),
                        challenge_prompt=frame_data.get('challenge', ''),
                    ))
                    break  # One match per framework

        return assumptions

    def should_challenge(self, question: str) -> Tuple[bool, Optional[str]]:
        """
        Determine if frame challenge is needed and return challenge text.

        Args:
            question: The user's question

        Returns:
            (should_challenge, challenge_text)
        """
        assumptions = self.analyze(question)

        if not assumptions:
            return False, None

        # Build combined challenge
        if len(assumptions) == 1:
            return True, assumptions[0].challenge_prompt

        # Multiple frameworks assumed
        combined = (
            "This question assumes several post-biblical frameworks:\n\n" +
            "\n\n".join(f"**{a.framework_name}:** {a.challenge_prompt}" for a in assumptions)
        )
        return True, combined


# Singleton
_analyzer = None


def get_frame_analyzer() -> FrameAnalyzer:
    """Get or create singleton analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = FrameAnalyzer()
    return _analyzer


def analyze_question_frames(question: str) -> List[FrameAssumption]:
    """Convenience function for analysis."""
    return get_frame_analyzer().analyze(question)


def should_challenge_frame(question: str) -> Tuple[bool, Optional[str]]:
    """Convenience function for challenge check."""
    return get_frame_analyzer().should_challenge(question)
