from flask import Blueprint, jsonify
from datetime import datetime, timezone

status_bp = Blueprint("status_api", __name__)

@status_bp.get("/status")
def status():
    return jsonify(
        {
            "status": "ok",
            "time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    )
