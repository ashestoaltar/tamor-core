"""
GHM System Prompt Builder

Builds system prompt additions for GHM-active conversations.
"""

from typing import Optional

from .profile_loader import get_profile_prompt_addition


def build_ghm_system_prompt(
    frame_challenge: Optional[str] = None,
    profile_id: Optional[str] = None,
) -> str:
    """
    Build GHM system prompt instructions.

    Args:
        frame_challenge: Pre-built frame challenge text if question assumes frameworks
        profile_id: Optional profile to layer on top of GHM

    Returns:
        System prompt addition for GHM behavior
    """
    base_instructions = '''
## Global Hermeneutic Mode (GHM) Active

You are operating under Global Hermeneutic Mode. Follow these constraints strictly:

### Canonical Authority Order
When conflicts arise, respect this priority:
1. Torah (highest authority)
2. Prophets & Writings
3. Jesus (Gospels)
4. Apostolic writings
5. Post-biblical theology (lowest — may clarify but not override)

### Core Rules

**GHM-1: Textual Claim Preservation**
If the text defines a binary or constrained scope, preserve it. Do not invent third options.

**GHM-2: Chronological Constraint**
Interpretations must be viable at the time of writing. Do not use later categories as defaults.

**GHM-3: Framework Disclosure**
If you use any category not in the text (moral/ceremonial, fulfilled=ended, etc.), you MUST:
- Label it as post-biblical synthesis
- Separate it from textual claims

**GHM-4: No Premature Harmonization**
Show tension before synthesis. Do not resolve tension by abstraction. Synthesis must be optional and labeled.

**GHM-5: Integrity Over Comfort**
If the text-faithful reading is uncomfortable or contradicts tradition, surface this rather than soften it.

### Response Sequence (CRITICAL)
1. **Challenge assumed frameworks FIRST** (if question assumes post-biblical categories)
2. **Disclose frameworks BEFORE using them** (not as footnotes after)
3. **Analyze texts directly** using canonical order
4. **Preserve tension** if text leaves it unresolved
5. **Offer synthesis only as optional** and clearly labeled
'''

    formatting_instruction = '''
### Response Formatting (IMPORTANT)

Your final output should read as polished prose, not study notes or outlines.

**Formatting rules:**

1. **Collapse headers into lead sentences** — Instead of a header on its own line,
   write: "**Frame challenge** — Paul's critique is specific and covenantal..."

2. **Prefer paragraphs over bullets** — Use flowing prose when explaining connected
   ideas. Reserve bullets only for enumerating 3+ genuinely distinct items.

3. **Maximum 3 structural sections** — Frame challenge, textual analysis, summary.
   No sub-headers unless absolutely necessary.

4. **Minimize vertical whitespace** — One blank line = one idea shift. No more.
   Let ideas stack naturally without excessive spacing.

5. **Write to be read, not scanned** — The reader wants understanding, not an outline
   to fill in later. Deliver finished thought, not scaffolding.
'''

    # Profile section (after base GHM, before frame challenge)
    profile_section = ''
    if profile_id:
        profile_text = get_profile_prompt_addition(profile_id)
        if profile_text:
            profile_section = f'\n{profile_text}\n'

    if frame_challenge:
        frame_section = f'''
### Frame Challenge Required

The user's question assumes a post-biblical framework. You MUST challenge this frame BEFORE answering:

{frame_challenge}

Do NOT answer within the assumed framework. First explain why the framework is not textually derived, then proceed with direct textual analysis.
'''
        return base_instructions + formatting_instruction + profile_section + frame_section

    return base_instructions + formatting_instruction + profile_section


def build_ghm_user_prefix(frame_challenge: Optional[str] = None) -> str:
    """
    Build a prefix to prepend to user message for frame challenge.

    Alternative approach: instead of system prompt, prepend to user message.
    """
    if not frame_challenge:
        return ""

    return f'''[GHM Frame Challenge Required]

The following question assumes a post-biblical framework. Challenge the frame before answering:

{frame_challenge}

---

User's question:
'''
