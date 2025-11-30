from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from utils.db import get_db

auth_bp = Blueprint("auth", __name__, url_prefix="/api")

# --- Helper functions --------------------------------------------------------


def get_user_by_username(username):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user


def create_user(username, display_name, password):
    if get_user_by_username(username):
        return None, "Username already exists"

    pw_hash = generate_password_hash(password)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (username, display_name, password_hash)
        VALUES (?, ?, ?)
        """,
        (username, display_name, pw_hash),
    )
    conn.commit()

    new_id = cur.lastrowid
    conn.close()
    return new_id, None


# --- Routes ------------------------------------------------------------------


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    display_name = data.get("display_name") or username

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    user_id, err = create_user(username, display_name, password)
    if err:
        return jsonify({"error": err}), 400

    session["user_id"] = user_id

    return jsonify(
        {
            "id": user_id,
            "username": username,
            "display_name": display_name,
        }
    ), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()

    if not username:
        return jsonify({"error": "username required"}), 400

    user = get_user_by_username(username)
    if not user:
        return jsonify({"error": "invalid credentials"}), 401

    # 🚫 No password check – trusted home setup.
    session["user_id"] = user["id"]

    return jsonify(
        {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
        }
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    return jsonify({"success": True})


@auth_bp.route("/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None})

    user = get_user_by_id(user_id)
    if not user:
        session.pop("user_id", None)
        return jsonify({"user": None})

    return jsonify(
        {
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
            }
        }
    )


@auth_bp.route("/users", methods=["GET"])
def list_users():
    """Return all users for the UI user-switcher."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, display_name FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()

    users = [
        {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
        }
        for row in rows
    ]

    return jsonify({"users": users})

