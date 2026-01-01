# api/core/task_classifier.py
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    from dateutil import parser as date_parser  # type: ignore
except Exception:  # pragma: no cover
    date_parser = None


_REMIND_RE = re.compile(r"\b(remind me|set (a )?reminder)\b", re.IGNORECASE)

_IN_RE = re.compile(
    r"\b(in)\s+(?P<num>\d+)\s*(?P<unit>minute|minutes|min|hour|hours|hr|hrs|day|days)\b",
    re.IGNORECASE,
)

_TOMORROW_AT_RE = re.compile(
    r"\btomorrow\b(?:\s+at\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm)?)?",
    re.IGNORECASE,
)

_AT_RE = re.compile(
    r"\bat\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm)\b",
    re.IGNORECASE,
)

# very light fallback for "3pm" without "at"
_BARE_TIME_RE = re.compile(r"\b(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm)\b", re.IGNORECASE)


def _local_tz() -> ZoneInfo:
    # Use system timezone if available; fallback UTC
    try:
        return ZoneInfo(str(datetime.now().astimezone().tzinfo))
    except Exception:
        return ZoneInfo("UTC")


def _to_utc_iso(dt_local: datetime) -> str:
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=_local_tz())
    return dt_local.astimezone(timezone.utc).isoformat(timespec="minutes")


def _parse_in(text: str, now: datetime) -> datetime | None:
    m = _IN_RE.search(text)
    if not m:
        return None
    num = int(m.group("num"))
    unit = m.group("unit").lower()

    if unit in ("minute", "minutes", "min"):
        return now + timedelta(minutes=num)
    if unit in ("hour", "hours", "hr", "hrs"):
        return now + timedelta(hours=num)
    if unit in ("day", "days"):
        return now + timedelta(days=num)
    return None


def _parse_tomorrow_at(text: str, now: datetime) -> datetime | None:
    m = _TOMORROW_AT_RE.search(text)
    if not m:
        return None

    base = (now + timedelta(days=1)).date()
    h = m.group("h")
    if not h:
        # "tomorrow" with no explicit time -> default 9:00 AM
        return datetime(base.year, base.month, base.day, 9, 0, tzinfo=now.tzinfo)

    hour = int(h)
    minute = int(m.group("m") or "0")
    ampm = (m.group("ampm") or "").lower()

    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    return datetime(base.year, base.month, base.day, hour, minute, tzinfo=now.tzinfo)


def _parse_at_time(text: str, now: datetime) -> datetime | None:
    # matches "at 3pm"
    m = _AT_RE.search(text)
    if not m:
        # fallback: "3pm" anywhere
        m = _BARE_TIME_RE.search(text)
        if not m:
            return None

    hour = int(m.group("h"))
    minute = int(m.group("m") or "0")
    ampm = (m.group("ampm") or "").lower()

    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    candidate = datetime(now.year, now.month, now.day, hour, minute, tzinfo=now.tzinfo)

    # If time already passed today, assume next day
    if candidate <= now:
        candidate = candidate + timedelta(days=1)

    return candidate


def _parse_with_dateutil(text: str, now: datetime) -> datetime | None:
    if not date_parser:
        return None
    try:
        dt = date_parser.parse(text, default=now)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=now.tzinfo)
        # If parsed time is in the past, bump by a day (conservative)
        if dt <= now:
            dt = dt + timedelta(days=1)
        return dt
    except Exception:
        return None


def classify_task(user_text: str) -> dict | None:
    text = (user_text or "").strip()
    if not text:
        return None

    if not _REMIND_RE.search(text):
        return None

    now = datetime.now(_local_tz())

    scheduled_local = (
        _parse_in(text, now)
        or _parse_tomorrow_at(text, now)
        or _parse_at_time(text, now)
        or _parse_with_dateutil(text, now)
    )

    normalized = {}
    confidence = 0.6

    if scheduled_local:
        normalized["scheduled_for"] = _to_utc_iso(scheduled_local)
        confidence = 0.95
    else:
        # we detected a reminder intent but couldn't parse time
        confidence = 0.7

    return {
        "task_type": "reminder",
        "title": text,
        "confidence": confidence,
        "payload": {
            "raw": text,
        },
        "normalized": normalized,
        "status": "needs_confirmation",
    }

