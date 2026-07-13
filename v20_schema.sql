-- taixuan-web v2.0 user system schema (SQLite)
-- Run once: sqlite3 /var/www/taixuan/data.db < v20_schema.sql
-- Note: readings table from v1.2 must exist (history feature)

-- 1. users table
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

-- 2. sessions table (JWT blacklist + explicit logout)
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- 3. favorites table (user saved readings + notes)
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reading_id INTEGER NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_reading ON favorites(reading_id);

-- 4. subscriptions table (v3.0 placeholder, schema only no payment logic)
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan TEXT,
    started_at TIMESTAMP,
    expires_at TIMESTAMP,
    is_active INTEGER DEFAULT 0
);

-- 5. ALTER readings (add user_id, NULL allowed for anonymous)
ALTER TABLE readings ADD COLUMN user_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_readings_user ON readings(user_id);