import json
import time
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from utils.db import get_db
from api.routes.chat_api import insert_system_message

log = logging.getLogger(__name__)

UTC = ZoneInfo("UTC")


# -----------------------------
# Helpers
# -----------------------------

def _is_business_day(dt: datetime) -> bool:
    return dt.weekday() < 5


def _first_business_day(year: int, month: int) -> datetime:
    dt = datetime(year, month, 1, tzinfo=UTC)
    while not _is_business_day(dt):
        dt += timedelta(days=1)
    return dt


def _last_day_of_month(year: int, month: int) -> datetime:
    if month == 12:
        return datetime(year + 1, 1, 1, tzinfo=UTC) - timedelta(days=1)
    return datetime(year, month + 1, 1, tzinfo=UTC) - timedelta(days=1)


def _next_weekday(from_dt: datetime, weekday: int) -> datetime:
    days_ahead = (weekday - from_dt.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return from_dt + timedelta(days=days_ahead)


# -----------------------------
# Core scheduling logic
# -----------------------------

def _compute_next_scheduled(prev: datetime, recurrence: dict) -> datetime | None:
    """
    Compute next run in UTC based on recurrence rules.
    """
    if not recurrence:
        return None

    rtype = recurrence.get("type")
    interval = int(recurrence.get("interval", 1))
    byweekday = recurrence.get("byweekday")

    # Normalize
    prev = prev.astimezone(UTC)

    # -----------------------------
    # Daily
    # -----------------------------
    if rtype == "daily":
        return prev + timedelta(days=interval)

    # -----------------------------
    # Weekly
    # -----------------------------
    if rtype == "weekly":
        if byweekday:
            # Next matching weekday in list
            candidates = [
                _next_weekday(prev, wd) for wd in sorted(byweekday)
            ]
            return min(candidates)
        return prev + timedelta(weeks=interval)

    # -----------------------------
    # Monthly
    # -----------------------------
    if rtype == "monthly":
        year = prev.year
        month = prev.month + interval
        while month > 12:
            year += 1
            month -= 12

        # First business day
        if recurrence.get("business_day") == "first":
            next_dt = _first_business_day(year, month)
            return next_dt.replace(
                hour=prev.hour,
                minute=prev.minute,
                second=prev.second,
                microsecond=0,
            )

        # Last day of month
        if recurrence.get("bysetpos") == -1:
            last = _last_day_of_month(year, month)
            return last.replace(
                hour=prev.hour,
                minute=prev.minute,
                second=prev.second,
                microsecond=0,
            )

        # Default: same day of month (clamped)
        try:
            return prev.replace(year=year, month=month)
        except ValueError:
            last = _last_day_of_month(year, month)
            return last.replace(
                hour=prev.hour,
                minute=prev.minute,
                second=prev.second,
                microsecond=0,
            )

    return None


# -----------------------------
# Executor loop
# -----------------------------

def run_task_executor(poll_interval: int = 30):
    log.info("Task executor started")

    while True:
        try:
            _claim_and_execute()
        except Exception:
            log.exception("Executor loop error")
        time.sleep(poll_interval)


def _claim_and_execute():
    conn = get_db()
    cur = conn.cursor()

    now = datetime.now(tz=UTC).isoformat()

    cur.execute(
        """
        SELECT *
        FROM detected_tasks
        WHERE status='confirmed'
          AND json_extract(normalized_json, '$.scheduled_for') <= ?
        ORDER BY id
        LIMIT 10
        """,
        (now,),
    )

    tasks = cur.fetchall()

    for task in tasks:
        task_id = task["id"]
        normalized = json.loads(task["normalized_json"] or "{}")
        scheduled_for = datetime.fromisoformat(
            normalized["scheduled_for"]
        ).astimezone(UTC)

        log.info(f"Claiming task {task_id}")

        cur.execute(
            """
            UPDATE detected_tasks
            SET status='running'
            WHERE id=? AND status='confirmed'
            """,
            (task_id,),
        )
        if cur.rowcount != 1:
            continue

        # Log run start
        cur.execute(
            """
            INSERT INTO task_runs (task_id, status, started_at)
            VALUES (?, 'running', CURRENT_TIMESTAMP)
            """,
            (task_id,),
        )
        run_id = cur.lastrowid
        conn.commit()

        try:
            # Emit reminder into chat
            insert_system_message(
                conversation_id=task["conversation_id"],
                content=f"⏰ Reminder: {task['title']}",
            )

            recurrence = normalized.get("recurrence")
            next_dt = _compute_next_scheduled(scheduled_for, recurrence)

            if next_dt:
                normalized["scheduled_for"] = next_dt.astimezone(UTC).isoformat()
                cur.execute(
                    """
                    UPDATE detected_tasks
                    SET normalized_json=?, status='confirmed'
                    WHERE id=?
                    """,
                    (json.dumps(normalized), task_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE detected_tasks
                    SET status='completed'
                    WHERE id=?
                    """,
                    (task_id,),
                )

            cur.execute(
                """
                UPDATE task_runs
                SET status='success', finished_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (run_id,),
            )

            log.info(f"Task {task_id} executed successfully")

        except Exception as e:
            log.exception(f"Task {task_id} failed")

            cur.execute(
                """
                UPDATE task_runs
                SET status='failed', error_text=?, finished_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (str(e), run_id),
            )

            cur.execute(
                """
                UPDATE detected_tasks
                SET status='confirmed'
                WHERE id=?
                """,
                (task_id,),
            )

        conn.commit()

    conn.close()

