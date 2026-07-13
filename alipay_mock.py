"""
taixuan-web v2.0 Alipay checkout integration (mock + real dual mode).

Mock mode (default, no env): returns mock checkout URL with fake out_trade_no
that the frontend can simulate a successful payment.

Real mode (TAIXUAN_ALIPAY_APP_ID + APP_PRIVATE_KEY_PATH set):
creates a real Alipay trade (Wap/H5 pay) and returns the payment URL.

Switching: just set TAIXUAN_ALIPAY_* env vars in .env.local, then restart.
No code change needed.

Architecture: same as stripe_mock.py for symmetry.
"""
import os
import secrets
import logging

# ============================================
# Load .env.local automatically (python-dotenv)
# ============================================
try:
    from dotenv import load_dotenv
    # Look for .env.local in same dir as this file (or project root)
    _here = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(_here, ".env.local"),
        os.path.join(os.path.dirname(_here), ".env.local"),
        ".env.local",
    ]:
        if os.path.exists(candidate):
            load_dotenv(candidate, override=False)
            break
except ImportError:
    pass  # dotenv optional; rely on real env vars

log = logging.getLogger(__name__)


# ============================================
# Config (read from env at module load)
# ============================================
def _load_private_key() -> str:
    """Load app private key: from PATH (preferred) or env var.

    PATH preferred because multi-line PEM in env requires escaping hell.
    """
    key_path = os.environ.get("TAIXUAN_ALIPAY_APP_PRIVATE_KEY_PATH", "")
    if key_path and os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    # Fallback: env var (legacy)
    return os.environ.get("TAIXUAN_ALIPAY_APP_PRIVATE_KEY", "")


APP_ID = os.environ.get("TAIXUAN_ALIPAY_APP_ID", "")
APP_PRIVATE_KEY = _load_private_key()
ALIPAY_PUBLIC_KEY = os.environ.get("TAIXUAN_ALIPAY_ALIPAY_PUBLIC_KEY", "")
GATEWAY = os.environ.get("TAIXUAN_ALIPAY_GATEWAY", "https://openapi.alipay.com/gateway.do")
PUBLIC_BASE_URL = os.environ.get("TAIXUAN_PUBLIC_BASE_URL", "http://116.62.69.83")

# Toggle: real mode if all 3 critical env vars are set
USE_REAL_ALIPAY = bool(APP_ID and APP_PRIVATE_KEY and ALIPAY_PUBLIC_KEY)


def is_mock_mode() -> bool:
    """Return True if using mock (no real Alipay API calls)."""
    return not USE_REAL_ALIPAY


def _import_alipay_sdk():
    """Lazy import: only require alipay package when in real mode.

    Returns: alipay module (or None if not installed).
    """
    try:
        from alipay import AliPay
        return AliPay
    except ImportError:
        log.error("[alipay_mock] python-alipay-sdk not installed. pip install python-alipay-sdk==3.4.0")
        return None


def create_checkout_session(plan: str, user_id: int, user_email: str) -> dict:
    """Create an Alipay trade (or mock equivalent).

    Returns:
      {
        "url": "...",         # URL to redirect user to (real: alipay.com; mock: /mock_confirm)
        "out_trade_no": "...",  # Alipay order ID (or mock ID)
        "mode": "mock" | "alipay",
        "plan": plan,
        "price_cents": 999,
      }
    """
    import user_system
    if plan not in user_system.PLANS:
        raise ValueError(f"Unknown plan: {plan}")
    plan_cfg = user_system.PLANS[plan]

    if plan == "free":
        # No Alipay for free plan
        return {
            "url": f"{PUBLIC_BASE_URL}/api/v2/subscribe/mock_confirm?plan=free&user_id={user_id}",
            "out_trade_no": "free_" + secrets.token_urlsafe(8),
            "mode": "mock_free",
            "plan": plan,
            "price_cents": 0,
        }

    # Generate unique out_trade_no (alipay order id)
    out_trade_no = secrets.token_urlsafe(16)

    if USE_REAL_ALIPAY:
        AliPay = _import_alipay_sdk()
        if AliPay is None:
            # SDK missing, fall back to mock
            return _mock_session(plan, user_id, out_trade_no, plan_cfg)

        try:
            alipay = AliPay(
                appid=APP_ID,
                app_notify_url=f"{PUBLIC_BASE_URL}/api/v2/subscribe/webhook",
                app_private_key_string=APP_PRIVATE_KEY,
                alipay_public_key_string=ALIPAY_PUBLIC_KEY,
                sign_type="RSA2",
            )

            # Wap pay (mobile browser): user clicks "Pay" -> redirected to Alipay -> pays -> back to success_url
            # NOTE: out_trade_no must be <= 64 chars and unique
            # passback_params: URL-encoded, e.g. "user_id=42&plan=monthly"
            from urllib.parse import quote
            passback_params = quote(f"user_id={user_id}")

            order_string = alipay.api_alipay_trade_wap_pay(
                out_trade_no=out_trade_no,
                total_amount=str(plan_cfg["price_cents"] / 100.0),  # cents to yuan
                subject=f"taixuan {plan_cfg['label']}",
                return_url=f"{PUBLIC_BASE_URL}/api/v2/subscribe/return?plan={plan}",
                notify_url=f"{PUBLIC_BASE_URL}/api/v2/subscribe/webhook",
                passback_params=passback_params,
            )

            # Build full URL
            url = f"{GATEWAY}?{order_string}"

            return {
                "url": url,
                "out_trade_no": out_trade_no,
                "mode": "alipay",
                "plan": plan,
                "price_cents": plan_cfg["price_cents"],
                "label": plan_cfg["label"],
            }
        except Exception as e:
            # Alipay API error; fall back to mock
            log.exception("[alipay_mock] Real Alipay failed, falling back to mock: %s", e)
            return _mock_session(plan, user_id, out_trade_no, plan_cfg)

    return _mock_session(plan, user_id, out_trade_no, plan_cfg)


def _mock_session(plan: str, user_id: int, out_trade_no: str, plan_cfg: dict) -> dict:
    """Mock checkout session for development.

    URL points to /api/v2/subscribe/mock_confirm with out_trade_no + plan params.
    """
    return {
        "url": f"{PUBLIC_BASE_URL}/api/v2/subscribe/mock_confirm?out_trade_no={out_trade_no}&plan={plan}&user_id={user_id}",
        "out_trade_no": out_trade_no,
        "mode": "mock",
        "plan": plan,
        "price_cents": plan_cfg["price_cents"],
        "label": plan_cfg["label"],
    }


def verify_webhook_signature(post_data: dict) -> bool:
    """Verify Alipay webhook (async notify) signature.

    Args:
        post_data: request.form dict from Flask (Alipay sends application/x-www-form-urlencoded)

    Returns:
        True if signature is valid and trade is successful.
    """
    if not USE_REAL_ALIPAY:
        return False

    AliPay = _import_alipay_sdk()
    if AliPay is None:
        return False

    try:
        alipay = AliPay(
            appid=APP_ID,
            app_notify_url=f"{PUBLIC_BASE_URL}/api/v2/subscribe/webhook",
            app_private_key_string=APP_PRIVATE_KEY,
            alipay_public_key_string=ALIPAY_PUBLIC_KEY,
            sign_type="RSA2",
        )

        signature = post_data.pop("sign", None)
        if not signature:
            return False

        # verify() returns True if signature valid
        success = alipay.verify(post_data, signature)
        if not success:
            log.warning("[alipay_mock] webhook signature verification failed")
            return False

        # Check trade status
        trade_status = post_data.get("trade_status", "")
        return trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED")
    except Exception as e:
        log.exception("[alipay_mock] verify_webhook failed: %s", e)
        return False