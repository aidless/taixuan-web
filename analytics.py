"""
taixuan-web v1.3 lightweight analytics module.
- request_visit(): log every HTTP request (PV)
- track_event(): log explicit conversion events
- aggregate_dashboard(): compute summary stats

Privacy:
- IP addresses are SHA256-hashed with a daily salt (never stored raw)
- No third-party tracking
- No cookies
- 30-day retention for visits, 90-day for events
"""
import hashlib
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

# Daily salt (rotated) for IP hashing
_SALT_FILE = os.path.join(os.path.dirname(__file__), "logs", ".analytics_salt")
_IP_HASH_CACHE = {}  # ip -> hash, regenerated daily


def _get_salt() -> str:
    """Get or rotate daily salt for IP hashing."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        if os.path.exists(_SALT_FILE):
            with open(_SALT_FILE, "r") as f:
                salt_date, salt_value = f.read().strip().split(":", 1)
            if salt_date == today:
                return salt_value
    except Exception:
        pass

    # Generate new daily salt
    new_salt = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
    try:
        os.makedirs(os.path.dirname(_SALT_FILE), exist_ok=True)
        with open(_SALT_FILE, "w") as f:
            f.write(f"{today}:{new_salt}")
    except Exception:
        pass  # best effort
    return new_salt


def hash_ip(ip: str) -> str:
    """One-way hash IP for analytics."""
    if not ip:
        return ""
    salt = _get_salt()
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:16]


def _get_db_path() -> str:
    """Same DB as user_system (data.db or TAIXUAN_DB_PATH)."""
    return os.environ.get("TAIXUAN_DB_PATH", "data.db")


def init_analytics() -> None:
    """Create visits + events tables if not exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "analytics_schema.sql")
    if not os.path.exists(schema_path):
        return
    conn = sqlite3.connect(_get_db_path())
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def log_visit(path: str, method: str, status: int, ip: str, user_agent: str,
              user_id: int | None = None, referrer: str | None = None) -> None:
    """Log a single HTTP request. Best-effort, never raises."""
    try:
        conn = sqlite3.connect(_get_db_path())
        try:
            conn.execute(
                "INSERT INTO visits (ip_hash, path, method, status, user_agent, user_id, referrer) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (hash_ip(ip), path[:500], method, status,
                 user_agent[:500] if user_agent else None,
                 user_id, referrer[:500] if referrer else None),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # analytics never break user request


def track_event(name: str, ip: str | None = None, user_id: int | None = None,
                liupai: str | None = None, payload: dict | None = None) -> None:
    """Log an explicit conversion event. Best-effort."""
    try:
        conn = sqlite3.connect(_get_db_path())
        try:
            conn.execute(
                "INSERT INTO events (name, ip_hash, user_id, liupai, payload) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, hash_ip(ip) if ip else None, user_id, liupai,
                 json.dumps(payload, ensure_ascii=False)[:2000] if payload else None),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def aggregate_dashboard(days: int = 7) -> dict:
    """Compute summary stats for last N days."""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(_get_db_path())
    try:
        # Total PV / UV
        pv_row = conn.execute(
            "SELECT COUNT(*) AS pv, COUNT(DISTINCT ip_hash) AS uv FROM visits WHERE ts >= ?",
            (since,),
        ).fetchone()
        pv, uv = pv_row["pv"], pv_row["uv"]

        # Unique visitors today
        today_start = datetime.utcnow().strftime("%Y-%m-%d 00:00:00")
        today_uv = conn.execute(
            "SELECT COUNT(DISTINCT ip_hash) FROM visits WHERE ts >= ?",
            (today_start,),
        ).fetchone()[0]

        # Top paths
        top_paths = conn.execute(
            "SELECT path, COUNT(*) AS hits FROM visits "
            "WHERE ts >= ? AND method = 'GET' "
            "GROUP BY path ORDER BY hits DESC LIMIT 10",
            (since,),
        ).fetchall()

        # Liupai funnel (from events)
        liupai_views = conn.execute(
            "SELECT liupai, COUNT(*) AS n FROM events "
            "WHERE name = 'liupai_view' AND ts >= ? GROUP BY liupai ORDER BY n DESC",
            (since,),
        ).fetchall()
        liupai_submits = conn.execute(
            "SELECT liupai, COUNT(*) AS n FROM events "
            "WHERE name = 'form_submit' AND ts >= ? GROUP BY liupai",
            (since,),
        ).fetchall()
        submits_by_liupai = {r["liupai"]: r["n"] for r in liupai_submits}

        # Build funnel with submit conversion rate
        funnel = []
        for row in liupai_views:
            liupai = row["liupai"]
            views = row["n"]
            submits = submits_by_liupai.get(liupai, 0)
            cvr = (submits / views * 100.0) if views > 0 else 0.0
            funnel.append({
                "liupai": liupai,
                "views": views,
                "submits": submits,
                "conversion_pct": round(cvr, 1),
            })

        # Event counts
        event_counts = conn.execute(
            "SELECT name, COUNT(*) AS n FROM events "
            "WHERE ts >= ? GROUP BY name ORDER BY n DESC",
            (since,),
        ).fetchall()

        # Auth events
        auth_events = conn.execute(
            "SELECT name, COUNT(*) AS n FROM events "
            "WHERE ts >= ? AND name IN ('register', 'login', 'favorite') "
            "GROUP BY name",
            (since,),
        ).fetchall()

        return {
            "days": days,
            "since": since,
            "pv": pv,
            "uv": uv,
            "today_uv": today_uv,
            "top_paths": [dict(r) for r in top_paths],
            "liupai_funnel": funnel,
            "events": [dict(r) for r in event_counts],
            "auth_events": [dict(r) for r in auth_events],
        }
    finally:
        conn.close()


# ===== Flask middleware / decorator =====

def install_middleware(app):
    """Install @app.before_request / @app.after_request hooks for analytics."""
    from flask import request, g

    @app.before_request
    def _analytics_before():
        g._analytics_start = time.time()
        g._analytics_path = request.path
        g._analytics_method = request.method

    @app.after_request
    def _analytics_after(response):
        # Don't track healthz (too noisy)
        if g.get("_analytics_path") in ("/healthz", "/api/v2/version"):
            return response
        try:
            user_id = None
            # Try to extract user from token (best-effort)
            from user_system import decode_token, get_user
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:].strip()
                payload = decode_token(token)
                if payload:
                    u = get_user(payload.get("sub"))
                    if u:
                        user_id = u["user_id"]

            log_visit(
                path=g.get("_analytics_path", ""),
                method=g.get("_analytics_method", "GET"),
                status=response.status_code,
                ip=request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip(),
                user_agent=request.headers.get("User-Agent", ""),
                user_id=user_id,
                referrer=request.headers.get("Referer", ""),
            )
        except Exception:
            pass
        return response