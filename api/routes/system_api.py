"""
routes/system_api.py

System-level endpoints for health and diagnostics.
These are used by the UI RightPanel (getHealth / getStatus).

Phase 8.4: Added /api/system-status for UI indicators.
"""

import os
from typing import Dict, Any

from flask import Blueprint, jsonify

from utils.db import get_db, DB_PATH
from services.system_status import get_status_dict

system_bp = Blueprint("system_api", __name__, url_prefix="/api")


def _check_db() -> Dict[str, Any]:
    """
    Run a very small 'SELECT 1' style query to ensure the DB is reachable.
    Also returns basic row counts for a few core tables, if they exist.

    Phase 4.0 addition:
      - detected_tasks_total
      - detected_tasks_by_status
    """
    info: Dict[str, Any] = {
        "db_ok": False,
        "db_path": DB_PATH,
        "db_error": None,
        "counts": {
            "projects": None,
            "memories": None,
            "project_files": None,
            # Added for tasks diagnostics
            "detected_tasks_total": None,
            "detected_tasks_by_status": {},
        },
    }

    try:
        conn = get_db()
        cur = conn.cursor()

        # Simple SELECT 1 to verify connection
        cur.execute("SELECT 1")
        cur.fetchone()

        # Try to gather some basic counts; if any table is missing,
        # we just skip that entry instead of failing the whole call.
        def safe_count(table: str, key: str | None = None) -> None:
            try:
                cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
                row = cur.fetchone()
                if row is not None:
                    out_key = key or table
                    if out_key in info["counts"]:
                        info["counts"][out_key] = row["c"]
            except Exception:
                # Table may not exist yet; ignore.
                pass

        safe_count("projects")
        safe_count("memories")
        safe_count("project_files")
        safe_count("detected_tasks", key="detected_tasks_total")

        # Group counts by status for detected_tasks
        try:
            cur.execute(
                """
                SELECT status, COUNT(*) AS c
                FROM detected_tasks
                GROUP BY status
                """
            )
            rows = cur.fetchall() or []
            by_status = {r["status"]: int(r["c"]) for r in rows} if rows else {}
            # Ensure stable keys (optional but nice for UI)
            for k in ["detected", "needs_confirmation", "confirmed", "completed", "cancelled", "dismissed"]:
                by_status.setdefault(k, 0)
            info["counts"]["detected_tasks_by_status"] = by_status
        except Exception:
            # Table may not exist yet or JSON1 missing, etc.
            info["counts"]["detected_tasks_by_status"] = {}

        conn.close()
        info["db_ok"] = True
    except Exception as exc:  # defensive
        info["db_ok"] = False
        info["db_error"] = str(exc)

    return info


def _get_uptime_seconds() -> float:
    """
    Read uptime from /proc/uptime if available, else fall back to 0.0.
    """
    try:
        with open("/proc/uptime", "r") as f:
            line = f.readline().strip().split()
            return float(line[0])
    except Exception:
        # On non-Linux or restricted environments we just return 0.0
        return 0.0


def _get_disk_percent_used(path: str = "/") -> float:
    """
    Return the disk usage percentage for the given filesystem path.
    """
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        available = st.f_bavail * st.f_frsize
        used = total - available
        if total <= 0:
            return 0.0
        return round((used / total) * 100.0, 2)
    except Exception:
        return 0.0


@system_bp.get("/health")
def health():
    """
    Lightweight health check used for polling in the RightPanel.

    Returns JSON like:
    {
        "status": "ok" | "error",
        "db_ok": true/false
    }
    """
    db_info = _check_db()
    status = "ok" if db_info.get("db_ok") else "error"
    return jsonify(
        {
            "status": status,
            "db_ok": db_info.get("db_ok", False),
        }
    )


@system_bp.get("/status")
def status():
    """
    Detailed diagnostics endpoint used by the RightPanel diagnostics modal.

    Returns JSON like:
    {
        "status": "ok" | "error",
        "db_ok": bool,
        "db_path": "...",
        "db_error": "... or null",
        "uptime_seconds": float,
        "disk_percent_used": float,
        "worker_pids": [int, ...],
        "counts": {...}
    }
    """
    db_info = _check_db()

    # Worker PIDs are optional; for now we return an empty list.
    worker_pids: list[int] = []

    payload: Dict[str, Any] = {
        "status": "ok" if db_info.get("db_ok") else "error",
        "db_ok": db_info.get("db_ok", False),
        "db_path": db_info.get("db_path"),
        "db_error": db_info.get("db_error"),
        "uptime_seconds": _get_uptime_seconds(),
        "disk_percent_used": _get_disk_percent_used("/"),
        "worker_pids": worker_pids,
        "counts": db_info.get("counts", {}),
    }

    return jsonify(payload)


@system_bp.get("/system-status")
def system_status():
    """
    Phase 8.4: System status for UI indicators.

    Returns component availability for status bar display:
    - Library mount status
    - LLM availability
    - Reference sources (SWORD, Sefaria)
    - Embeddings availability
    """
    return jsonify(get_status_dict())

