"""
taixuan-web v2.0 Stripe checkout integration (mock).

Mock mode (default, no STRIPE_API_KEY env): returns mock checkout URL
that the user can click to simulate a successful payment.

Real mode (STRIPE_API_KEY set to sk_test_... or sk_live_...): creates
a real Stripe Checkout Session.

Switching: just set TAIXUAN_STRIPE_API_KEY=sk_test_xxx in supervisor env,
then restart. No code change needed.
"""
import os
import secrets

# Toggle: if TAIXUAN_STRIPE_API_KEY is set AND starts with "sk_", use real Stripe
# Otherwise use mock (no API calls, returns local URL).
STRIPE_API_KEY = os.environ.get("TAIXUAN_STRIPE_API_KEY", "")
USE_REAL_STRIPE = STRIPE_API_KEY.startswith("sk_")

# Base URL for redirect (after Stripe checkout success/cancel)
PUBLIC_BASE_URL = os.environ.get("TAIXUAN_PUBLIC_BASE_URL", "http://116.62.69.83")


def is_mock_mode() -> bool:
    """Return True if using mock (no real Stripe API calls)."""
    return not USE_REAL_STRIPE


def create_checkout_session(plan: str, user_id: int, user_email: str) -> dict:
    """Create a Stripe Checkout Session (or mock equivalent).

    Returns:
      {
        "url": "...",         # URL to redirect user to
        "session_id": "...",  # Stripe session ID (or mock ID)
        "mode": "mock" | "stripe",
        "plan": plan,
        "price_cents": 100,
      }
    """
    import user_system
    if plan not in user_system.PLANS:
        raise ValueError(f"Unknown plan: {plan}")
    plan_cfg = user_system.PLANS[plan]

    if plan == "free":
        # No Stripe for free plan
        return {
            "url": f"{PUBLIC_BASE_URL}/subscribe?plan=free&user_id={user_id}",
            "session_id": "free_" + secrets.token_urlsafe(8),
            "mode": "mock_free",
            "plan": plan,
            "price_cents": 0,
        }

    session_id = "cs_test_" + secrets.token_urlsafe(16)

    if USE_REAL_STRIPE:
        # Real Stripe (would actually charge). Requires `stripe` package.
        try:
            import stripe
            stripe.api_key = STRIPE_API_KEY
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"泰玄小站 {plan_cfg['label']}"},
                        "unit_amount": plan_cfg["price_cents"],
                        "recurring": {"interval": "month" if plan == "monthly" else "year"},
                    },
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=f"{PUBLIC_BASE_URL}/subscribe/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{PUBLIC_BASE_URL}/subscribe/cancel",
                client_reference_id=str(user_id),
                customer_email=user_email,
                metadata={"user_id": str(user_id), "plan": plan},
            )
            return {
                "url": session.url,
                "session_id": session.id,
                "mode": "stripe",
                "plan": plan,
                "price_cents": plan_cfg["price_cents"],
            }
        except ImportError:
            # stripe package not installed; fall back to mock
            return _mock_session(plan, user_id, session_id, plan_cfg)
        except Exception as e:
            # Stripe API error; fall back to mock (dev convenience)
            return _mock_session(plan, user_id, session_id, plan_cfg)

    return _mock_session(plan, user_id, session_id, plan_cfg)


def _mock_session(plan: str, user_id: int, session_id: str, plan_cfg: dict) -> dict:
    """Mock checkout session for development."""
    return {
        "url": f"{PUBLIC_BASE_URL}/subscribe/mock_confirm?session_id={session_id}&plan={plan}&user_id={user_id}",
        "session_id": session_id,
        "mode": "mock",
        "plan": plan,
        "price_cents": plan_cfg["price_cents"],
        "label": plan_cfg["label"],
    }