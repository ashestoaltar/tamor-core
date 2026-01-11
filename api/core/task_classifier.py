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
    r"\bin\s+(?P<num>\d+)\s+(?P<unit>minutes?|mins?|hours?|hrs?|days?)\b",
    re.IGNORECASE,
)

_TOMORROW_AT_RE = re.compile(
    r"\btomorrow\b.*?\bat\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm)\b",
    re.IGNORECASE,
)

_AT_RE = re.compile(
    r"\bat\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm)\b",
    re.IGNORECASE,
)

_BARE_TIME_RE = re.compile(
    r"\b(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm)\b",
    re.IGNORECASE,
)


def _local_tz() -> ZoneInfo:
    try:
        return ZoneInfo(str(datetime.now().astimezone().tzinfo))
    except Exception:
        return ZoneInfo("UTC")


def _resolve_user_tz(tz_name: str | None, tz_offset_minutes: int | None) -> ZoneInfo | timezone:
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            pass
    if tz_offset_minutes is not None:
        try:
            # JS getTimezoneOffset(): minutes behind UTC (CST=360). Convert to tzinfo.
            return timezone(timedelta(minutes=-int(tz_offset_minutes)))
        except Exception:
            pass
    return _local_tz()


def _resolve_tz(tz_name: str | None, tz_offset_minutes: int | None) -> timezone | ZoneInfo:
    # Prefer IANA timezone (DST-correct)
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            pass

    # Fallback: numeric offset from JS Date.getTimezoneOffset()
    # JS offset is minutes behind UTC (CST=360). Python offset sign is reversed.
    if tz_offset_minutes is not None:
        try:
            return timezone(timedelta(minutes=-int(tz_offset_minutes)))
        except Exception:
            pass

    return _local_tz()


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

    if unit in ("minute", "minutes", "min", "mins"):
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

    hour = int(m.group("h"))
    minute = int(m.group("m") or "0")
    ampm = (m.group("ampm") or "").lower()

    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    base = (now + timedelta(days=1)).date()
    return datetime(base.year, base.month, base.day, hour, minute, tzinfo=now.tzinfo)


def _parse_at_time(text: str, now: datetime) -> datetime | None:
    m = _AT_RE.search(text)
    if not m:
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
    if candidate <= now:
        candidate = candidate + timedelta(days=1)
    return candidate


def _parse_with_dateutil(text: str, now: datetime) -> datetime | None:
    if not date_parser:
        return None
    try:
        # dateutil returns naive sometimes; attach tz if missing
        dt = date_parser.parse(text, default=now)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=now.tzinfo)
        return dt
    except Exception:
        return None


def classify_task(text: str, tz_name: str | None = None, tz_offset_minutes: int | None = None) -> dict | None:
    if not text or not _REMIND_RE.search(text):
        return None

    user_tz = _resolve_user_tz(tz_name, tz_offset_minutes)
    now = datetime.now(user_tz)

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
        confidence = 0.7

    return {
        "task_type": "reminder",
        "title": text,
        "confidence": confidence,
        "payload": {"raw": text},
        "normalized": normalized,
        "status": "needs_confirmation",
    }

