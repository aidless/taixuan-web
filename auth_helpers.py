"""
taixuan-web v2.0 auth helpers (optional auth).

get_optional_user() - if Bearer token present and valid, return user dict.
                    - if no token or invalid, return None (do NOT 401).

This lets reading/reading_stream endpoints work for both anonymous and logged-in users.
"""
import user_system


def get_optional_user() -> dict | None:
    """Parse Authorization header (if any). Return user dict or None. Never 401."""
    from flask import request
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    payload = user_system.decode_token(token)
    if not payload:
        return None
    if user_system.is_token_revoked(token):
        return None
    return user_system.get_user(payload.get("sub"))