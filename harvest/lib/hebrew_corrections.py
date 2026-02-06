"""
Hebrew term correction for auto-captions and Whisper transcripts.

Loads correction dictionary from NAS shared config.
Falls back to built-in defaults if NAS config not available.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.harvest_config import CONFIG_DIR

# Path to shared correction dictionary on NAS
CORRECTIONS_FILE = os.path.join(CONFIG_DIR, "hebrew-terms.json")

# Built-in defaults (used if NAS file not found)
DEFAULT_CORRECTIONS = {
    "yeshua": ["yes sure", "yes you a", "yoshua", "yashua"],
    "torah": ["tore a", "torah", "tora"],
    "shabbat": ["shabbos", "shabbot", "sha bat", "shabbott"],
    "sukkot": ["sue coat", "sukot", "soo coat", "sue cot"],
    "shavuot": ["sha vote", "shavot", "shavu ot"],
    "pesach": ["pay sock", "pesak", "pay sack"],
    "tanakh": ["tannock", "tannic", "tannick"],
    "midrash": ["mid rash", "mid rush", "mid rosh"],
    "haftarah": ["half torah", "haftora", "half tora"],
    "parashah": ["parasha", "par a sha", "para sha"],
    "halakhah": ["halacha", "hala ka", "halla ka"],
    "teshuvah": ["teshuva", "te shu va"],
    "mitzvot": ["mits vote", "mitzvote", "mits vot"],
    "hashem": ["ha shem", "hash em"],
    "adonai": ["add a nigh", "add oh nigh"],
    "elohim": ["ello heem", "elo him"],
    "ruach": ["rue ack", "roo ach"],
    "mashiach": ["mashi ack", "mashi ach"],
    "b'rit chadashah": ["brit chadasha", "britt chadasha"],
    "monte judah": ["monty judah", "monte juda"],
    "tim hegg": ["tim heg", "tim haig"],
    "tom bradford": ["tom bradford"],
}

_corrections_cache = None


def load_corrections():
    """Load correction dictionary (NAS file or defaults)."""
    global _corrections_cache
    if _corrections_cache is not None:
        return _corrections_cache

    if os.path.exists(CORRECTIONS_FILE):
        with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            _corrections_cache = json.load(f)
    else:
        _corrections_cache = DEFAULT_CORRECTIONS

    return _corrections_cache


def apply_corrections(text):
    """
    Apply Hebrew term corrections to text.

    For each correction target, checks if any of its error variants
    appear in the text (case-insensitive) and replaces them.

    Returns: (corrected_text, corrections_made_count)
    """
    corrections = load_corrections()
    count = 0

    for correct_term, variants in corrections.items():
        for variant in variants:
            # Skip if the variant IS the correct term
            if variant.lower() == correct_term.lower():
                continue

            # Case-insensitive replacement, preserving word boundaries
            pattern = re.compile(r"\b" + re.escape(variant) + r"\b", re.IGNORECASE)
            new_text, n = pattern.subn(correct_term, text)
            if n > 0:
                text = new_text
                count += n

    return text, count


def save_corrections(corrections_dict, path=None):
    """Save corrections dictionary to NAS."""
    if path is None:
        path = CORRECTIONS_FILE

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(corrections_dict, f, indent=2, ensure_ascii=False)
