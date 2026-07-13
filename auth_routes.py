"""
taixuan-web v2.0 authentication routes (Flask Blueprint).
Mount: app.register_blueprint(auth_bp, url_prefix="/api/v2/auth")
"""
from flask import Blueprint, request, jsonify

import user_system

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    """POST /api/v2/auth/register
    Body: {"email": str, "password": str, "nickname": str?}
    Resp: 200 {user_id, access_token, expires_at}
          400 {error: msg}
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    nickname = (data.get("nickname") or "").strip() or None

    ok, msg, user = user_system.create_user(email, password, nickname)
    if not ok:
        return jsonify({"error": msg}), 400

    token = user_system.create_token(user["user_id"], user["email"])
    user_system.register_session(user["user_id"], token)

    return jsonify({
        "user_id": user["user_id"],
        "email": user["email"],
        "nickname": user["nickname"],
        "access_token": token,
        "expires_in": user_system.JWT_TTL_SEC,
    }), 200


@auth_bp.route("/login", methods=["POST"])
def login():
    """POST /api/v2/auth/login
    Body: {"email": str, "password": str}
    Resp: 200 {user_id, access_token, expires_in}
          401 {error: "invalid credentials"}
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = user_system.verify_login(email, password)
    if not user:
        return jsonify({"error": "invalid credentials"}), 401

    token = user_system.create_token(user["user_id"], user["email"])
    user_system.register_session(user["user_id"], token)

    return jsonify({
        "user_id": user["user_id"],
        "email": user["email"],
        "nickname": user["nickname"],
        "access_token": token,
        "expires_in": user_system.JWT_TTL_SEC,
    }), 200


@auth_bp.route("/logout", methods=["POST"])
@user_system.require_auth
def logout(user):
    """POST /api/v2/auth/logout
    Header: Authorization: Bearer <token>
    Resp: 200 {ok: true}
    """
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip()
    user_system.revoke_session(token)
    return jsonify({"ok": True}), 200


@auth_bp.route("/me", methods=["GET"])
@user_system.require_auth
def me(user):
    """GET /api/v2/auth/me
    Header: Authorization: Bearer <token>
    Resp: 200 {user_id, email, nickname, role, created_at, last_login_at}
    """
    return jsonify(user), 200