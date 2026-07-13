"""
taixuan-web v2.0 user system module.
- bcrypt password hashing (cost=12)
- JWT issue/decode (HS256, 14 days expiry)
- require_auth decorator
- User CRUD (register / fetch / update last_login)
- Sessions table for JWT blacklist
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import re
from functools import wraps
from pathlib import Path

# ===== Config =====
JWT_SECRET = os.environ.get("TAIXUAN_JWT_SECRET", "CHANGE-ME-IN-PROD-via-env")
JWT_TTL_SEC = 14 * 24 * 3600  # 14 days
DB_PATH = os.environ.get("TAIXUAN_DB_PATH", "/var/www/taixuan/data.db")
# Local dev path fallback (without ECS env)
if not Path(DB_PATH).parent.exists():
    DB_PATH = "data.db"

BCRYPT_AVAILABLE = False
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    pass

# ===== DB init =====

def init_db(db_path: str = None) -> None:
    """Create users/sessions/favorites/subscriptions tables if not exist."""
    db_path = db_path or DB_PATH
    schema = Path(__file__).parent / "v20_schema.sql"

    conn = sqlite3.connect(db_path)

    # Always create minimal schema first (independent of v20_schema.sql existence)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nickname TEXT,
            avatar_url TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reading_id INTEGER NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);
        CREATE INDEX IF NOT EXISTS idx_favorites_reading ON favorites(reading_id);

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan TEXT,
            started_at TIMESTAMP,
            expires_at TIMESTAMP,
            is_active INTEGER DEFAULT 0
        );
    """)
    conn.commit()

    # Optionally attempt v20_schema.sql (may contain ALTER readings which requires readings table)
    if schema.exists():
        try:
            with open(schema, "r", encoding="utf-8") as f:
                sql = f.read()
            conn.executescript(sql)
            conn.commit()
        except sqlite3.OperationalError:
            # ALTER readings failed (readings table does not exist yet) - OK
            pass

    conn.close()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ===== Password =====

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email))


def validate_password(password: str) -> tuple:
    """Returns (ok, msg). Password must be >= 8 chars and include a digit."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    return True, ""


def hash_password(plain: str) -> str:
    """Hash with bcrypt cost=12. Falls back to SHA256+salt if bcrypt unavailable."""
    if BCRYPT_AVAILABLE:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    # Fallback (NOT for prod): salted SHA256
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
    return f"sha256${salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    if hashed.startswith("sha256$"):
        _, salt, h = hashed.split("$", 2)
        return hmac.compare_digest(
            h, hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
        )
    if BCRYPT_AVAILABLE:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False
    return False


# ===== JWT (minimal HS256, no external deps) =====

def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    import base64
    padding = 4 - (len(data) % 4)
    return base64.urlsafe_b64decode(data + "=" * padding)


def create_token(user_id: int, email: str) -> str:
    """Issue HS256 JWT. Payload: {sub: user_id, email, iat, exp}."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": user_id, "email": email, "iat": now, "exp": now + JWT_TTL_SEC}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(JWT_SECRET.encode("utf-8"), f"{h}.{p}".encode("utf-8"), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


def decode_token(token: str):
    """Decode JWT, return payload or None if invalid/expired."""
    try:
        h, p, s = token.split(".", 2)
        sig = _b64url_decode(s)
        expected = hmac.new(JWT_SECRET.encode("utf-8"), f"{h}.{p}".encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(p).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def token_hash(token: str) -> str:
    """SHA256 for sessions blacklist storage (never store raw JWT)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ===== User CRUD =====

def create_user(email: str, password: str, nickname=None) -> tuple:
    """Returns (ok, msg, user_dict)."""
    if not validate_email(email):
        return False, "Invalid email format", None
    ok, msg = validate_password(password)
    if not ok:
        return False, msg, None
    pw_hash = hash_password(password)
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, nickname) VALUES (?, ?, ?)",
            (email, pw_hash, nickname or email.split("@")[0]),
        )
        conn.commit()
        user_id = cur.lastrowid
        user = {"user_id": user_id, "email": email, "nickname": nickname or email.split("@")[0]}
        return True, "User created", user
    except sqlite3.IntegrityError:
        return False, "Email already registered", None
    finally:
        conn.close()


def verify_login(email: str, password: str):
    """Returns user dict on success, None on failure."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, email, password_hash, nickname, role, is_active FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if not row or not row["is_active"]:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        conn.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
        conn.commit()
        return {
            "user_id": row["id"],
            "email": row["email"],
            "nickname": row["nickname"],
            "role": row["role"],
        }
    finally:
        conn.close()


def get_user(user_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, email, nickname, role, created_at, last_login_at FROM users WHERE id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "user_id": row["id"],
            "email": row["email"],
            "nickname": row["nickname"],
            "role": row["role"],
            "created_at": row["created_at"],
            "last_login_at": row["last_login_at"],
        }
    finally:
        conn.close()


# ===== Sessions (JWT blacklist) =====

def register_session(user_id: int, token: str) -> None:
    """Add a session entry so token can be revoked on logout."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?, ?, datetime('now', '+14 days'))",
            (user_id, token_hash(token)),
        )
        conn.commit()
    finally:
        conn.close()


def is_token_revoked(token: str) -> bool:
    """True if token was explicitly logged out (DELETE on logout)."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE token_hash = ?", (token_hash(token),)
        ).fetchone()
        return False
    finally:
        conn.close()


def revoke_session(token: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
        conn.commit()
    finally:
        conn.close()


# ===== Favorites =====

def add_favorite(user_id: int, reading_id: int, note=None):
    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM favorites WHERE user_id = ? AND reading_id = ?",
            (user_id, reading_id),
        ).fetchone()
        if existing:
            return None
        cur = conn.execute(
            "INSERT INTO favorites (user_id, reading_id, note) VALUES (?, ?, ?)",
            (user_id, reading_id, note),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def list_favorites(user_id: int, limit: int = 50) -> list:
    conn = get_conn()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(readings)").fetchall()]
        if "summary" in cols:
            rows = conn.execute(
                "SELECT f.id AS favorite_id, f.reading_id, f.note, f.created_at, "
                "       r.liupai, r.question, r.summary "
                "FROM favorites f LEFT JOIN readings r ON f.reading_id = r.id "
                "WHERE f.user_id = ? ORDER BY f.created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT f.id AS favorite_id, f.reading_id, f.note, f.created_at, "
                "       r.liupai, r.question "
                "FROM favorites f LEFT JOIN readings r ON f.reading_id = r.id "
                "WHERE f.user_id = ? ORDER BY f.created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def remove_favorite(user_id: int, favorite_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM favorites WHERE id = ? AND user_id = ?",
            (favorite_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ===== Auth decorator =====

def require_auth(fn):
    """Flask decorator: enforce Bearer token. Injects user dict as kwarg user.

    Usage:
        @app.route("/me")
        @require_auth
        def me(user):
            return jsonify(user)
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from flask import request, jsonify
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing_or_invalid_authorization"}), 401
        token = auth[7:].strip()
        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "invalid_or_expired_token"}), 401
        if is_token_revoked(token):
            return jsonify({"error": "token_revoked"}), 401
        user = get_user(payload["sub"])
        if not user:
            return jsonify({"error": "user_not_found"}), 401
        kwargs["user"] = user
        return fn(*args, **kwargs)
    return wrapper