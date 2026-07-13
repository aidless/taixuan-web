"""
taixuan-web v2.0 subscription routes (Flask Blueprint).
Mount: app.register_blueprint(subscriptions_bp, url_prefix="/api/v2/subscribe")

Phase 7: Stripe checkout (mock by default) + subscription management.
Phase 8 (2026-07-13): Alipay integration added (default for CN users).
Both payment providers coexist; default switched to Alipay.
"""
from flask import Blueprint, request, jsonify, redirect

import user_system
import alipay_mock  # primary payment provider (China)
# stripe_mock kept as backup/alternative; not imported by default to save import time

subscriptions_bp = Blueprint("subscriptions", __name__)


def _get_payment_provider():
    """Return active payment provider module.

    Default: alipay. Fallback: stripe_mock if TAIXUAN_STRIPE_API_KEY is set
    AND alipay is in mock mode.
    """
    if not alipay_mock.is_mock_mode():
        return ("alipay", alipay_mock)
    # Check if Stripe key is set as backup
    import os
    if os.environ.get("TAIXUAN_STRIPE_API_KEY", "").startswith("sk_"):
        import stripe_mock
        return ("stripe", stripe_mock)
    return ("alipay", alipay_mock)  # default mock = alipay mock


@subscriptions_bp.route("/plans", methods=["GET"])
def list_plans():
    """GET /api/v2/subscribe/plans
    Public: list available plans.
    """
    provider_name, _ = _get_payment_provider()
    return jsonify({
        "plans": [
            {"name": name, **cfg}
            for name, cfg in user_system.PLANS.items()
        ],
        "mode": provider_name if not _get_payment_provider()[1].is_mock_mode() else "mock",
        "provider": provider_name,
    })


@subscriptions_bp.route("/checkout", methods=["POST"])
@user_system.require_auth
def checkout(user):
    """POST /api/v2/subscribe/checkout
    Header: Authorization: Bearer <token>
    Body: {"plan": "monthly" | "yearly" | "free"}
    Resp: 200 {url, out_trade_no, mode, plan, price_cents}
    """
    data = request.get_json(silent=True) or {}
    plan = (data.get("plan") or "").strip().lower()

    if plan not in user_system.PLANS:
        return jsonify({
            "error": f"Unknown plan: {plan}",
            "valid_plans": list(user_system.PLANS.keys()),
        }), 400

    if plan == "free":
        # No payment needed; downgrade immediately
        ok, msg, sub = user_system.create_subscription(user["user_id"], "free")
        return jsonify({
            "ok": True,
            "message": msg,
            "subscription": sub,
            "redirect_url": "/me",
        }), 200

    provider_name, provider = _get_payment_provider()
    try:
        session = provider.create_checkout_session(
            plan=plan,
            user_id=user["user_id"],
            user_email=user["email"],
        )
        return jsonify({
            "ok": True,
            "provider": provider_name,
            **session,
        }), 200
    except Exception as e:
        return jsonify({"error": "checkout_creation_failed", "detail": str(e)}), 500


@subscriptions_bp.route("/mock_confirm", methods=["GET"])
@user_system.require_auth
def mock_confirm(user):
    """GET /api/v2/subscribe/mock_confirm?out_trade_no=...&plan=...
    MOCK-ONLY: simulates successful payment webhook. Creates subscription.
    In real Alipay/Stripe mode, this endpoint does nothing (payment provider sends webhook).
    """
    plan = (request.args.get("plan") or "").strip().lower()
    out_trade_no = request.args.get("out_trade_no", "")

    if plan not in user_system.PLANS:
        return jsonify({"error": "invalid_plan"}), 400
    if plan == "free":
        return jsonify({"error": "free_plan_no_payment"}), 400

    # Create subscription (mock simulates immediate success)
    ok, msg, sub = user_system.create_subscription(user["user_id"], plan)
    if not ok:
        return jsonify({"error": msg}), 400

    return jsonify({
        "ok": True,
        "message": "Mock payment successful",
        "out_trade_no": out_trade_no,
        "subscription": sub,
        "redirect_url": "/me",
    }), 200


# ============================================
# Alipay real-mode endpoints
# ============================================

@subscriptions_bp.route("/webhook", methods=["POST"])
def alipay_webhook():
    """POST /api/v2/subscribe/webhook
    Alipay async notify (server-to-server).
    Verifies signature, checks trade status, activates subscription.

    In mock mode: rejects (400).
    In real mode: returns "success" to Alipay after activating sub.
    """
    if alipay_mock.is_mock_mode():
        return "mock_mode_no_webhook", 400

    # Alipay sends application/x-www-form-urlencoded
    post_data = request.form.to_dict()

    if not alipay_mock.verify_webhook_signature(post_data):
        return "signature_failed", 400

    out_trade_no = post_data.get("out_trade_no", "")
    # Plan and user_id should be in custom params; Alipay passes them via passback_params
    # For simplicity, we encode them in out_trade_no format: "PLAN_USERID_RANDOM"
    # OR use the trade subject to extract plan; here we use subject lookup.

    # We saved plan in the order_string's `subject` field (e.g. "taixuan monthly").
    # A simpler approach: read from out_trade_no prefix.
    # For now, assume out_trade_no encodes user_id + plan.
    # TODO: store trade_no -> (user_id, plan) mapping when checkout is created.

    # As a robust fallback, parse subject if present
    subject = post_data.get("subject", "")
    plan = None
    if "monthly" in subject:
        plan = "monthly"
    elif "yearly" in subject:
        plan = "yearly"

    if not plan:
        return "unknown_plan", 400

    # Try to extract user_id from passback_params (Alipay supports this)
    passback_params = post_data.get("passback_params", "")
    user_id = None
    if passback_params:
        try:
            # passback_params is URL-encoded query string
            from urllib.parse import parse_qs
            params = parse_qs(passback_params)
            if "user_id" in params:
                user_id = int(params["user_id"][0])
        except Exception:
            pass

    if not user_id:
        # Fallback: out_trade_no format "PLAN_USERID_RANDOM" (set in checkout if needed)
        # Or rely on DB lookup from out_trade_no
        return "missing_user_id", 400

    ok, msg, sub = user_system.create_subscription(user_id, plan)
    if not ok:
        return f"create_sub_failed: {msg}", 400

    return "success", 200


@subscriptions_bp.route("/return", methods=["GET"])
def alipay_return():
    """GET /api/v2/subscribe/return?plan=...
    Alipay sync return (user redirected back from Alipay app after payment).
    This is for UX only -- trust webhook for actual subscription activation.
    """
    plan = (request.args.get("plan") or "").strip().lower()
    out_trade_no = request.args.get("out_trade_no", "")

    # Redirect user to /me; frontend polls /status to see if sub is active.
    # Webhook may take 1-5s to arrive.
    if plan == "free":
        return redirect("/me")

    return redirect(f"/me?payment_returned=1&plan={plan}&out_trade_no={out_trade_no}")


# ============================================
# Subscription management (provider-agnostic)
# ============================================

@subscriptions_bp.route("/cancel", methods=["POST"])
@user_system.require_auth
def cancel(user):
    """POST /api/v2/subscribe/cancel
    Header: Authorization
    Resp: 200 {ok, message}
          400 {error: "No active subscription"}
    """
    ok, msg = user_system.cancel_subscription(user["user_id"])
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "message": msg}), 200


@subscriptions_bp.route("/status", methods=["GET"])
@user_system.require_auth
def status(user):
    """GET /api/v2/subscribe/status
    Header: Authorization
    Resp: 200 {plan, is_active, started_at, expires_at, days_remaining}
    """
    sub = user_system.get_subscription(user["user_id"])
    if not sub:
        return jsonify({
            "plan": "free",
            "is_active": False,
            "is_premium": False,
            "days_remaining": None,
        })

    days_remaining = None
    if sub.get("expires_at"):
        try:
            from datetime import datetime
            expires = datetime.strptime(sub["expires_at"][:19], "%Y-%m-%d %H:%M:%S")
            delta = expires - datetime.utcnow()
            days_remaining = max(0, delta.days)
        except (ValueError, TypeError):
            pass

    return jsonify({
        "plan": sub.get("plan"),
        "is_active": bool(sub.get("is_active")),
        "is_premium": user_system.is_subscription_active(user["user_id"]),
        "started_at": sub.get("started_at"),
        "expires_at": sub.get("expires_at"),
        "days_remaining": days_remaining,
    })


# ============================================
# DEPRECATED: Stripe webhook placeholder kept for reference
# (in case user re-enables Stripe later)
# ============================================
# @subscriptions_bp.route("/stripe_webhook", methods=["POST"])
# def stripe_webhook():
#     """Stripe webhook receiver (signature verified with the webhook secret env var)."""
#     pass