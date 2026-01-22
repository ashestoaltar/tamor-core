# api/utils/auth.py
"""
Standardized authentication utilities for API routes.

Usage:

    @require_login
    def my_route():
        user_id = get_current_user_id()
        ...

Or for routes that need user_id directly:

    def my_route():
        user_id, err = ensure_user()
        if err:
            return err
        ...
"""

from functools import wraps
from flask import session, jsonify


def require_login(fn):
    """
    Decorator that requires an authenticated session.

    Returns 401 with {"error": "not_authenticated"} if not logged in.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "not_authenticated"}), 401
        return fn(*args, **kwargs)
    return wrapper


def ensure_user():
    """
    Check for authenticated user and return (user_id, error_response).

    Returns:
        (user_id, None) if authenticated
        (None, error_tuple) if not authenticated

    Example:
        user_id, err = ensure_user()
        if err:
            return err
    """
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "not_authenticated"}), 401)
    return user_id, None


def get_current_user_id():
    """
    Get the current user ID from session.

    Returns None if not authenticated.
    Should only be used after @require_login decorator.
    """
    return session.get("user_id")
