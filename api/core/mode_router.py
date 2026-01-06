# api/core/mode_router.py
import re
from typing import Literal, Tuple

Mode = Literal["Scholar", "Forge", "System", "Anchor", "Path", "Creative"]

# Very small deterministic router: predictable > "smart"
# Returns (mode, confidence 0..1)
def route_mode(text: str) -> Tuple[Mode, float]:
    t = (text or "").strip()
    low = t.lower()

    if not t:
        return "Forge", 0.1

    # --- Strong signals ---
    # Code / terminal / debugging => Forge/System
    if "```" in t or re.search(r"\b(traceback|exception|stack trace|error:|segmentation fault)\b", low):
        return "System", 0.9
    if re.search(r"\b(sudo|systemctl|journalctl|curl|sqlite3|grep|rg|pip|venv|npm|node|vite|gunicorn|caddy)\b", low):
        return "Forge", 0.9
    if re.search(r"\b(api/|ui/|\.py\b|\.js\b|\.jsx\b|\.json\b|\.env\b|docker|linux|ubuntu|sql|regex)\b", low):
        return "Forge", 0.8

    # Scripture / theology => Scholar
    if re.search(r"\b(scripture|verse|hebrew|greek|tanakh|torah|gospel|epistle|isaiah|genesis|exodus|psalm|romans|john \d+|matthew \d+|luke \d+)\b", low):
        return "Scholar", 0.85

    # Creative work => Creative
    if re.search(r"\b(lyrics|chorus|verse 1|bridge|hook|riff|album|cover art|prompt|music video|suno|distrokid)\b", low):
        return "Creative", 0.85

    # Planning / overwhelm => Anchor
    if re.search(r"\b(plan|roadmap|checklist|priorities|organize|overwhelmed|next steps|schedule my|project plan)\b", low):
        return "Anchor", 0.75

    # Guidance / weighing choices => Path
    if re.search(r"\b(should i|what should i do|discern|wisdom|obedience|conviction|stewardship)\b", low):
        return "Path", 0.7

    # Default fallback
    return "Forge", 0.5
