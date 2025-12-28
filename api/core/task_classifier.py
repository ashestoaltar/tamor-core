import re
import json
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

# -----------------------------
# Constants / Regex
# -----------------------------

_WEEKDAY_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

_TZ_ALIASES = {
    "utc": "UTC",
    "est": "America/New_York",
    "edt": "America/New_York",
    "cst": "America/Chicago",
    "cdt": "America/Chicago",
    "mst": "America/Denver",
    "mdt": "America/Denver",
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
}

_TIME_RE = re.compile(
    r"\b(?:(\d{1,2})(?::(\d{2}))?\s*(am|pm)?|noon|midnight)\b(?!\s*(?:minutes?|hours?|days?|weeks?))",
    re.I,
)


_IN_DELTA_RE = re.compile(
    r"\bin\s+(\d+)\s*(minute|minutes|hour|hours|day|days|week|weeks)\b",
    re.I,
)

_EVERY_INTERVAL_RE = re.compile(
    r"\bevery\s+(\d+)\s*(day|days|week|weeks|month|months)\b",
    re.I,
)

_EVERY_WEEKDAY_LIST_RE = re.compile(
    r"\bevery\s+((?:mon|tue|tues|wed|thu|thurs|fri|sat|sun)(?:/\w+)*)\b",
    re.I,
)

# -----------------------------
# Helpers
# -----------------------------

def _parse_timezone(text: str):
    for k, v in _TZ_ALIASES.items():
        if re.search(rf"\b{k}\b", text, re.I):
            return ZoneInfo(v)
    return ZoneInfo("UTC")


def _parse_time_of_day(text: str):
    m = _TIME_RE.search(text)
    if not m:
        return None

    raw = m.group(0).lower()
    if raw == "noon":
        return time(12, 0)
    if raw == "midnight":
        return time(0, 0)

    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = m.group(3)

    if ampm:
        ampm = ampm.lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
            
        # ✅ HARDEN: reject bogus matches like "in 90 minutes"
        if hour < 0 or hour > 23:
            return None
        if minute < 0 or minute > 59:
            return None
    
    return time(hour, minute)


def _parse_in_delta(text: str):
    m = _IN_DELTA_RE.search(text)
    if not m:
        return None

    n = int(m.group(1))
    unit = m.group(2).lower()

    if "minute" in unit:
        return timedelta(minutes=n)
    if "hour" in unit:
        return timedelta(hours=n)
    if "day" in unit:
        return timedelta(days=n)
    if "week" in unit:
        return timedelta(weeks=n)
    return None


# -----------------------------
# Main classifier
# -----------------------------

def classify_task(user_text: str):
    """
    Returns:
      {
        task_type,
        title,
        scheduled_for (UTC datetime),
        recurrence (dict | None)
      }
    or None if not a task
    """

    text = (user_text or "").strip()
    if not text:
        return None

    low = text.lower()

    is_reminder = bool(re.search(r"\b(remind|reminder)\b", low))
    is_timer = bool(re.search(r"\b(timer|countdown)\b", low))

    if not (is_reminder or is_timer):
        return None

    tz = _parse_timezone(low)
    now = datetime.now(tz)

    # -----------------------------
    # Absolute or relative time
    # -----------------------------

    scheduled = None

    delta = _parse_in_delta(low)
    if delta:
        scheduled = now + delta

    tod = _parse_time_of_day(low)
    if tod and not scheduled:
        scheduled = now.replace(
            hour=tod.hour,
            minute=tod.minute,
            second=0,
            microsecond=0,
        )
        if scheduled <= now:
            scheduled += timedelta(days=1)

    if not scheduled:
        scheduled = now + timedelta(minutes=1)

    # -----------------------------
    # Recurrence parsing
    # -----------------------------

    recurrence = None

    # every weekday / weekend
    if "every weekday" in low:
        recurrence = {
            "type": "weekly",
            "interval": 1,
            "byweekday": [0, 1, 2, 3, 4],
        }

    elif "every weekend" in low:
        recurrence = {
            "type": "weekly",
            "interval": 1,
            "byweekday": [5, 6],
        }

    # every Mon/Wed/Fri
    else:
        m = _EVERY_WEEKDAY_LIST_RE.search(low)
        if m:
            days = m.group(1).split("/")
            byweekday = []
            for d in days:
                d = d.lower()
                if d in _WEEKDAY_MAP:
                    byweekday.append(_WEEKDAY_MAP[d])
            if byweekday:
                recurrence = {
                    "type": "weekly",
                    "interval": 1,
                    "byweekday": sorted(set(byweekday)),
                }

    # every N weeks / days / months
    if not recurrence:
        m = _EVERY_INTERVAL_RE.search(low)
        if m:
            n = int(m.group(1))
            unit = m.group(2).lower()

            if "week" in unit:
                recurrence = {"type": "weekly", "interval": n}
            elif "day" in unit:
                recurrence = {"type": "daily", "interval": n}
            elif "month" in unit:
                recurrence = {"type": "monthly", "interval": n}

    # monthly anchors
    if not recurrence and "last day" in low and "month" in low:
        recurrence = {
            "type": "monthly",
            "interval": 1,
            "bysetpos": -1,
        }

    if not recurrence and "first business day" in low:
        recurrence = {
            "type": "monthly",
            "interval": 1,
            "business_day": "first",
        }

    # -----------------------------
    # Normalize to UTC
    # -----------------------------

    scheduled_utc = scheduled.astimezone(ZoneInfo("UTC"))

    title = re.sub(r"\s+", " ", text)
    if len(title) > 120:
        title = title[:117] + "..."

    return {
        "task_type": "reminder" if is_reminder else "timer",
        "title": title,
        "scheduled_for": scheduled_utc,
        "recurrence": recurrence,
    }

