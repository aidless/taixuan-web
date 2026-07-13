"""
taixuan-web v2.0 subscription routes (Flask Blueprint).
Mount: app.register_blueprint(subscriptions_bp, url_prefix="/api/v2/subscribe")

Phase 7: Stripe checkout (mock by default) + subscription management.
"""
from flask import Blueprint, request, jsonify

import user_system
import stripe_mock

subscriptions_bp = Blueprint("subscriptions", __name__)


@subscriptions_bp.route("/plans", methods=["GET"])
def list_plans():
    """GET /api/v2/subscribe/plans
    Public: list available plans.
    """
    return jsonify({
        "plans": [
            {"name": name, **cfg}
            for name, cfg in user_system.PLANS.items()
        ],
        "mode": "stripe" if not stripe_mock.is_mock_mode() else "mock",
    })


@subscriptions_bp.route("/checkout", methods=["POST"])
@user_system.require_auth
def checkout(user):
    """POST /api/v2/subscribe/checkout
    Header: Authorization: Bearer <token>
    Body: {"plan": "monthly" | "yearly" | "free"}
    Resp: 200 {url, session_id, mode, plan, price_cents}
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

    try:
        session = stripe_mock.create_checkout_session(
            plan=plan,
            user_id=user["user_id"],
            user_email=user["email"],
        )
        return jsonify({
            "ok": True,
            **session,
        }), 200
    except Exception as e:
        return jsonify({"error": "checkout_creation_failed", "detail": str(e)}), 500


@subscriptions_bp.route("/mock_confirm", methods=["GET"])
@user_system.require_auth
def mock_confirm(user):
    """GET /api/v2/subscribe/mock_confirm?session_id=...&plan=...
    MOCK-ONLY: simulates successful Stripe webhook. Creates subscription.
    In real Stripe mode, this endpoint does nothing (Stripe sends webhook).
    """
    if not stripe_mock.is_mock_mode():
        return jsonify({"error": "mock_disabled_in_production"}), 400

    plan = (request.args.get("plan") or "").strip().lower()
    session_id = request.args.get("session_id", "")

    if plan not in user_system.PLANS:
        return jsonify({"error": "invalid_plan"}), 400
    if plan == "free":
        return jsonify({"error": "free_plan_no_payment"}), 400

    ok, msg, sub = user_system.create_subscription(user["user_id"], plan)
    if not ok:
        return jsonify({"error": msg}), 400

    return jsonify({
        "ok": True,
        "message": "Mock payment successful",
        "session_id": session_id,
        "subscription": sub,
        "redirect_url": "/me",
    }), 200


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


# In real Stripe mode, you'd add:
# @subscriptions_bp.route("/webhook", methods=["POST"])
# def stripe_webhook():
#     """Stripe webhook receiver (signature verified with whsec_*)."""
#     payload = request.data
#     sig = request.headers.get("Stripe-Signature")
#     try:
#         event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
#         if event["type"] == "checkout.session.completed":
#             user_id = int(event["data"]["object"]["client_reference_id"])
#             plan = event["data"]["object"]["metadata"]["plan"]
#             user_system.create_subscription(user_id, plan)
#         return jsonify({"received": True}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 400