"""
GHM Profile Loader

Loads profile definitions from api/config/profiles/ and builds
system prompt additions for active profiles.

Profiles operate WITHIN GHM — they add observational questions and
evidence weighting, never prescribe conclusions.
"""

import os
from functools import lru_cache
from typing import Dict, List, Optional

import yaml


_PROFILES_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'config', 'profiles'
)


@lru_cache(maxsize=16)
def load_profile(profile_id: str) -> Optional[Dict]:
    """
    Load a profile definition from YAML.

    Args:
        profile_id: Profile identifier (e.g., 'pronomian_trajectory')

    Returns:
        Parsed profile dict, or None if not found
    """
    path = os.path.join(_PROFILES_DIR, f'{profile_id}.yml')
    if not os.path.isfile(path):
        return None

    with open(path, 'r') as f:
        return yaml.safe_load(f)


def get_available_profiles() -> List[Dict]:
    """
    Scan profiles directory and return metadata for all available profiles.

    Returns:
        List of {id, display_name, category, requires_ghm}
    """
    profiles = []
    if not os.path.isdir(_PROFILES_DIR):
        return profiles

    for filename in sorted(os.listdir(_PROFILES_DIR)):
        if not filename.endswith('.yml'):
            continue

        profile_id = filename[:-4]  # strip .yml
        data = load_profile(profile_id)
        if not data:
            continue

        profiles.append({
            'id': data.get('id', profile_id),
            'display_name': data.get('display_name', profile_id),
            'category': data.get('category', ''),
            'requires_ghm': data.get('requires_ghm', True),
            'version': data.get('version', '0.1'),
        })

    return profiles


def get_profile_prompt_addition(profile_id: str) -> Optional[str]:
    """
    Build system prompt addition for a profile.

    Args:
        profile_id: Profile identifier

    Returns:
        Formatted system prompt text, or None if profile not found
    """
    data = load_profile(profile_id)
    if not data:
        return None

    sections = []

    # Header
    display_name = data.get('display_name', profile_id)
    sections.append(f'## Active Profile: {display_name}')
    sections.append('')

    # Principle
    principle = data.get('principle', '')
    if principle:
        sections.append(f'**Core Principle:** {principle.strip()}')
        sections.append('')

    # Evidence weighting
    weighting = data.get('weighting', {})
    if weighting:
        sections.append('### Evidence Weighting')
        for key, rule in weighting.items():
            desc = rule.get('description', key)
            weight = rule.get('weight', '')
            sections.append(f'- {desc} (weight: {weight})')
        sections.append('')

    # Question prompts
    prompts = data.get('question_prompts', [])
    if prompts:
        sections.append('### Questions to Surface')
        sections.append('When relevant, surface these questions (do not answer them for the user):')
        for p in prompts:
            trigger = p.get('trigger', '')
            question = p.get('question', '').strip()
            sections.append(f'- **{trigger}:** "{question}"')
            # v0.2: context filters
            for cf in p.get('context_filters', []):
                sections.append(f'  - Context: {cf}')
            # v0.2: skip conditions
            for sw in p.get('skip_when', []):
                sections.append(f'  - Skip when: {sw}')
            # v0.2: categories (repetition detector, audience scope)
            cats = p.get('categories', {})
            if cats:
                for cat_id, cat in cats.items():
                    desc = cat.get('description', cat_id)
                    signal = cat.get('signal', '')
                    examples = ', '.join(cat.get('examples', []))
                    line = f'  - *{cat_id}*: {desc}'
                    if examples:
                        line += f' (e.g., {examples})'
                    if signal:
                        line += f' — {signal}'
                    sections.append(line)
        sections.append('')

    # Discrimination rules (v0.2)
    disc = data.get('discrimination_rules', {})
    suppress = disc.get('suppress_continuity_questions_when', [])
    strengthen = disc.get('strengthen_continuity_questions_when', [])
    if suppress or strengthen:
        sections.append('### Discrimination Rules')
        if suppress:
            sections.append('**Suppress continuity questions when:**')
            for rule in suppress:
                cond = rule.get('condition', '')
                reason = rule.get('reason', '')
                sections.append(f'- {cond} — {reason}')
            sections.append('')
        if strengthen:
            sections.append('**Strengthen continuity questions when:**')
            for rule in strengthen:
                cond = rule.get('condition', '')
                reason = rule.get('reason', '')
                sections.append(f'- {cond} — {reason}')
            sections.append('')

    # Plausibility notes
    notes = data.get('plausibility_notes', [])
    if notes:
        sections.append('### Plausibility Notes')
        sections.append('You may reference these when relevant (attribute as historical context):')
        for n in notes:
            sections.append(f'- {n.get("note", "")}')
        sections.append('')

    # Guardrails
    guardrails = data.get('guardrails', [])
    if guardrails:
        sections.append('### Profile Guardrails (STRICT)')
        for g in guardrails:
            sections.append(f'- {g}')
        sections.append('')

    # Output disclosure
    markers = data.get('output_markers', {})
    disclosure = markers.get('disclosure', '')
    if disclosure:
        sections.append(f'### Disclosure Requirement')
        sections.append(f'Include this disclosure when profile influences the response:')
        sections.append(f'"{disclosure}"')
        sections.append('')

    return '\n'.join(sections)


def is_valid_profile(profile_id: str) -> bool:
    """Check if a profile ID corresponds to an existing profile."""
    return load_profile(profile_id) is not None
