from flask import Blueprint, jsonify
from datetime import datetime, timezone

status_bp = Blueprint("status_api", __name__)


def _check_database() -> tuple[bool, str]:
    """Check if the database is accessible."""
    try:
        from utils.db import get_db
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def _check_llm() -> tuple[bool, str]:
    """Check if LLM provider is configured."""
    try:
        from services.llm_service import llm_is_configured, get_model_name
        if llm_is_configured():
            return True, get_model_name()
        return False, "not configured"
    except Exception as e:
        return False, str(e)


@status_bp.get("/status")
def status():
    """Basic status check (backward compatible)."""
    return jsonify(
        {
            "status": "ok",
            "time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    )


@status_bp.get("/health")
def health():
    """
    Comprehensive health check endpoint.

    Returns component status for monitoring and diagnostics.
    HTTP 200 if all critical components healthy, 503 otherwise.
    """
    db_ok, db_detail = _check_database()
    llm_ok, llm_detail = _check_llm()

    # Database is critical; LLM is optional but reported
    all_healthy = db_ok

    response = {
        "status": "healthy" if all_healthy else "unhealthy",
        "time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "components": {
            "database": {"ok": db_ok, "detail": db_detail},
            "llm": {"ok": llm_ok, "detail": llm_detail},
        },
    }

    return jsonify(response), 200 if all_healthy else 503
