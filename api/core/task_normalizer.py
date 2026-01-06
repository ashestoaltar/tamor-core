# core/task_normalizer.py
import re
from datetime import datetime, timedelta, timezone


def normalize_detected_task(task: dict, utc_offset_minutes: int = 0) -> dict:
    """
    Normalize task shape so downstream systems can rely on:
      - normalized.scheduled_for (ISO string in UTC)
      - normalized.recurrence (dict) for recurring tasks

    This function MUST create recurrence when user intent implies it.

    utc_offset_minutes: Browser-reported offset (e.g., 360 for CST = UTC-6).
                       Positive for west of UTC, as returned by JS getTimezoneOffset().
    """
    if not isinstance(task, dict):
        return {}

    normalized = dict(task.get("normalized") or {})
    title = (task.get("title") or "").lower()

    # -----------------------------
    # Detect recurrence intent
    # -----------------------------
    is_daily = any(w in title for w in ("every day", "everyday", "daily"))
    is_weekly = "weekly" in title
    is_monthly = "monthly" in title

    # -----------------------------
    # Scheduled time (already parsed by classifier or earlier logic)
    # -----------------------------
    scheduled_for = normalized.get("scheduled_for")
    if isinstance(scheduled_for, str):
        try:
            scheduled_dt = datetime.fromisoformat(scheduled_for.replace("Z", "+00:00"))
        except Exception:
            scheduled_dt = None
    elif isinstance(scheduled_for, datetime):
        scheduled_dt = scheduled_for
    else:
        scheduled_dt = None

    # -----------------------------
    # Timezone handling: treat naive datetimes as LOCAL time
    # -----------------------------
    if scheduled_dt and scheduled_dt.tzinfo is None:
        # JS getTimezoneOffset() returns minutes EAST of UTC (e.g., 360 for UTC-6)
        # So we negate it to get the correct offset for Python timezone
        user_offset = timedelta(minutes=utc_offset_minutes)
        user_tz = timezone(user_offset)

        # Attach user's local timezone
        local_dt = scheduled_dt.replace(tzinfo=user_tz)

        # Convert to UTC for storage
        scheduled_dt = local_dt.astimezone(timezone.utc)

    elif scheduled_dt and scheduled_dt.tzinfo is not None:
        # If already aware, ensure it's converted to UTC
        scheduled_dt = scheduled_dt.astimezone(timezone.utc)

    # -----------------------------
    # Build recurrence object
    # -----------------------------
    if is_daily:
        normalized["recurrence"] = {
            "type": "daily",
            "interval": 1,
        }
    elif is_weekly:
        normalized["recurrence"] = {
            "type": "weekly",
            "interval": 1,
        }
    elif is_monthly:
        normalized["recurrence"] = {
            "type": "monthly",
            "interval": 1,
        }

    # -----------------------------
    # Ensure scheduled_for exists for recurring tasks
    # -----------------------------
    if "recurrence" in normalized and not scheduled_dt:
        # Default: next full hour in UTC
        now = datetime.now(timezone.utc)
        scheduled_dt = (now + timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )

    if scheduled_dt:
        normalized["scheduled_for"] = scheduled_dt.isoformat(timespec="minutes")

    return normalized
