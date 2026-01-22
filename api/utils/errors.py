# api/utils/errors.py
"""
Standardized API error responses.

This module provides consistent error formatting across all API endpoints.
All errors follow the format: {"error": "error_code", "detail": "optional message"}

Error codes should be:
- snake_case
- descriptive but concise
- machine-parseable (no spaces or special chars)
"""

from flask import jsonify
from typing import Optional, Any


# -----------------------------------------------------------------------------
# Standard HTTP Error Responses
# -----------------------------------------------------------------------------

def error_response(
    code: str,
    status: int = 400,
    detail: Optional[str] = None,
    **extra
):
    """
    Create a standardized error response.

    Args:
        code: Machine-readable error code (snake_case)
        status: HTTP status code
        detail: Human-readable explanation (optional)
        **extra: Additional fields to include in response

    Returns:
        Tuple of (jsonify response, status code)
    """
    payload = {"error": code}
    if detail:
        payload["detail"] = detail
    payload.update(extra)
    return jsonify(payload), status


# Authentication (401)
def not_authenticated(detail: str = None):
    """User is not logged in."""
    return error_response("not_authenticated", 401, detail)


# Authorization (403)
def forbidden(detail: str = None):
    """User lacks permission for this action."""
    return error_response("forbidden", 403, detail)


# Not Found (404)
def not_found(resource: str = "resource", detail: str = None):
    """Requested resource does not exist."""
    return error_response("not_found", 404, detail or f"{resource} not found")


# Validation (400)
def validation_error(code: str, detail: str = None):
    """Request validation failed."""
    return error_response(code, 400, detail)


def missing_field(field: str):
    """Required field is missing."""
    return error_response(f"{field}_required", 400, f"Missing required field: {field}")


def invalid_field(field: str, detail: str = None):
    """Field value is invalid."""
    return error_response(f"invalid_{field}", 400, detail)


# Conflict (409)
def conflict(code: str, detail: str = None, **extra):
    """Action conflicts with current state."""
    return error_response(code, 409, detail, **extra)


# Server Error (500)
def server_error(code: str = "internal_error", detail: str = None):
    """Internal server error."""
    return error_response(code, 500, detail)


# -----------------------------------------------------------------------------
# Domain-Specific Errors
# -----------------------------------------------------------------------------

def invalid_transition(
    resource_id: Any,
    from_status: str,
    to_status: str,
    reason: str = None
):
    """
    State transition is not allowed.

    Used for status machine violations (e.g., task state transitions).
    """
    payload = {
        "error": "invalid_transition",
        "resource_id": resource_id,
        "from": from_status,
        "to": to_status,
    }
    if reason:
        payload["reason"] = reason
    return jsonify(payload), 400


def resource_busy(resource: str, resource_id: Any, detail: str = None):
    """
    Resource is currently busy and cannot be modified.

    Example: Task is running and cannot be edited.
    """
    return error_response(
        f"{resource}_busy",
        409,
        detail,
        **{f"{resource}_id": resource_id}
    )
