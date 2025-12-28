from __future__ import annotations
from typing import Any, Dict, Optional

def normalize_detected_task(detected_task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Compatibility helper. If detected_task already includes 'normalized', return it.
    Otherwise attempt to build a minimal normalized payload from known fields.
    """
    if not detected_task:
        return None

    norm = detected_task.get("normalized")
    if isinstance(norm, dict):
        return norm

    task_type = detected_task.get("task_type") or detected_task.get("type")
    payload = detected_task.get("payload") or {}

    if task_type == "reminder":
        return {
            "type": "reminder",
            "scheduled_for": payload.get("scheduled_for"),
            "text": payload.get("text") or detected_task.get("title") or "",
        }

    return None
