"""
taixuan-web v2.0 authentication routes (Flask Blueprint).
Mount: app.register_blueprint(auth_bp, url_prefix="/api/v2/auth")

Phase 5: brute-force protection via IP-based login lockout.
Phase 6: forgot/reset password flow (dev mode returns reset_url in response;
          production should swap send_reset_email for SMTP).
"""
import logging
import os
from flask import Blueprint, request, jsonify

import user_system

auth_bp = Blueprint("auth", __name__)

# Reset URL base (frontend)
RESET_URL_BASE = os.environ.get("TAIXUAN_RESET_URL_BASE", "http://116.62.69.83/reset")


def send_reset_email(to_email: str, reset_url: str) -> bool:
    """Send password reset email. Dev mode just logs and returns True.

    Production: replace with SMTP send (SMTP_HOST, SMTP_PORT, SMTP_USER,
    SMTP_PASS env vars + smtplib.SMTP_SSL).
    Currently: only logs. The reset_url is also returned in the API response
    so dev/test can verify the flow.
    """
    logging.info(
        f"[DEV reset email] to={to_email} reset_url={reset_url}"
    )
    # In dev mode we always "send" successfully
    return True


@auth_bp.route("/register", methods=["POST"])
def register():
    """POST /api/v2/auth/register
    Body: {"email": str, "password": str, "nickname": str?}
    Resp: 200 {user_id, access_token, expires_in}
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
          429 {error: "Too many failed login attempts..."} (Phase 5)
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    client_ip = user_system.get_client_ip()

    locked, lock_msg = user_system.check_login_lockout(client_ip)
    if locked:
        return jsonify({"error": lock_msg, "retry_after_sec": user_system.LOCKOUT_WINDOW_SEC}), 429

    user = user_system.verify_login(email, password)
    if not user:
        user_system.record_login_attempt(client_ip, email, success=False)
        return jsonify({"error": "invalid credentials"}), 401

    user_system.clear_login_attempts(client_ip)
    user_system.record_login_attempt(client_ip, email, success=True)

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


@auth_bp.route("/forgot", methods=["POST"])
def forgot():
    """POST /api/v2/auth/forgot
    Body: {"email": str}
    Resp: 200 {"ok": true, "reset_url": "..." (dev only)}
          200 {"ok": true} (production; email actually sent)
          400 {error: "email required"}

    Always responds 200 OK for valid email format regardless of whether
    user exists, to prevent email enumeration attacks.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or not user_system.validate_email(email):
        return jsonify({"error": "Valid email required"}), 400

    token = user_system.request_password_reset(email)
    response = {"ok": True}

    if token:
        reset_url = f"{RESET_URL_BASE}?token={token}"
        send_reset_email(email, reset_url)
        # Dev mode: include reset_url in response for testing
        # (In production with SMTP, remove this to prevent leakage via API logs)
        if os.environ.get("TAIXUAN_RESET_RETURN_URL", "1") == "1":
            response["reset_url"] = reset_url
            response["expires_in_sec"] = user_system.RESET_TOKEN_TTL_SEC

    return jsonify(response), 200


@auth_bp.route("/reset", methods=["POST"])
def reset():
    """POST /api/v2/auth/reset
    Body: {"token": str, "new_password": str}
    Resp: 200 {"ok": true}
          400 {error: msg}
    """
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_password = data.get("new_password") or ""

    if not token:
        return jsonify({"error": "token required"}), 400
    if not new_password:
        return jsonify({"error": "new_password required"}), 400

    ok, msg = user_system.consume_reset_token(token, new_password)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True}), 200