-- taixuan-web v1.3 lightweight analytics schema
-- Run once: sqlite3 /var/www/taixuan/data.db < analytics_schema.sql

-- visits: one row per HTTP request (lightweight, capped by retention)
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_hash TEXT,                      -- SHA256(ip + salt), not raw IP
    path TEXT,
    method TEXT,
    status INTEGER,
    user_agent TEXT,
    user_id INTEGER,                   -- NULL if anonymous
    referrer TEXT
);
CREATE INDEX IF NOT EXISTS idx_visits_ts ON visits(ts);
CREATE INDEX IF NOT EXISTS idx_visits_path ON visits(path);
CREATE INDEX IF NOT EXISTS idx_visits_ip ON visits(ip_hash, ts);

-- events: explicit conversion events (liupai_view, form_submit, stream_complete, favorite)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    name TEXT NOT NULL,                 -- event name
    ip_hash TEXT,
    user_id INTEGER,
    liupai TEXT,
    payload TEXT                        -- JSON metadata
);
CREATE INDEX IF NOT EXISTS idx_events_name_ts ON events(name, ts);
CREATE INDEX IF NOT EXISTS idx_events_liupai ON events(liupai);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);

-- auto-purge: delete visits older than 30 days (cron-driven, see deploy_v131.sh)
--   DELETE FROM visits WHERE ts < datetime('now', '-30 days');
--   DELETE FROM events WHERE ts < datetime('now', '-90 days');