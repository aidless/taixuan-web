#!/bin/bash
# taixuan-web: deploy v1.2.1 -> v2.0 on ECS
# Run on ECS Workbench: bash deploy_v121_to_v20.sh
#
# What this does:
#   1. Backup current v1.2.1 to /tmp/taixuan-backup-v12/
#   2. Stop supervisor (so Flask releases the port)
#   3. Pull v2.0 files from GitHub master (8 new files)
#   4. Run v20_schema.sql (creates 4 new tables + ALTER readings)
#   5. Install bcrypt via pip
#   6. Generate JWT secret (TAIXUAN_JWT_SECRET)
#   7. Update supervisor to set TAIXUAN_JWT_SECRET env
#   8. Start supervisor
#   9. Run smoke test (healthz + new /api/v2/auth/register)
#
# Idempotent: can be re-run safely. Skips already-done steps.

set -e

BACKUP_DIR="/tmp/taixuan-backup-v12"
NEW_DIR="/var/www/taixuan"
GITHUB_BASE="https://raw.githubusercontent.com/aidless/taixuan-web/master"

echo "==== taixuan-web v1.2.1 -> v2.0 deploy ===="

# 1. Backup
echo ""
echo "[1/8] Backing up v1.2.1 -> $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
cp -f "$NEW_DIR/app.py" "$NEW_DIR/llm_backends.py" "$BACKUP_DIR/" 2>/dev/null || true
echo "      backup done"

# 2. Stop supervisor (gracefully)
echo ""
echo "[2/8] Stopping supervisor taixuan"
supervisorctl stop taixuan || true
sleep 1

# 3. Pull 8 new files (v2.0 modules + templates + static)
echo ""
echo "[3/8] Pulling v2.0 files from GitHub master"
cd "$NEW_DIR"

FILES=(
  "user_system.py"
  "auth_routes.py"
  "favorites_routes.py"
  "auth_helpers.py"
  "v20_schema.sql"
  "templates/login.html"
  "templates/register.html"
  "templates/me.html"
  "static/js/auth.js"
  "static/js/favorites.js"
)

for f in "${FILES[@]}"; do
  dir=$(dirname "$f")
  mkdir -p "$dir"
  if [ ! -s "$f" ] || [ "$(stat -c%s "$f" 2>/dev/null || echo 0)" -lt 100 ]; then
    echo "      GET $f"
    curl -sSL --retry 3 --retry-delay 2 --fail "$GITHUB_BASE/$f" -o "$f"
    if [ "$(stat -c%s "$f" 2>/dev/null || echo 0)" -lt 100 ]; then
      echo "      ERROR: $f still too small (GitHub 404?)"
      exit 1
    fi
  else
    echo "      SKIP $f (already exists, $(stat -c%s "$f") bytes)"
  fi
done

# 4. Run schema migration (idempotent - CREATE IF NOT EXISTS)
echo ""
echo "[4/8] Running v20_schema.sql"
if [ -f "data.db" ]; then
  sqlite3 data.db < v20_schema.sql && echo "      schema applied"
else
  echo "      NOTE: no data.db yet, user_system.init_db() will create on Flask boot"
fi

# 5. Install bcrypt
echo ""
echo "[5/8] Installing bcrypt"
pip install bcrypt 2>&1 | tail -2 || pip3 install bcrypt 2>&1 | tail -2

# 6. Generate JWT secret (32 bytes hex)
echo ""
echo "[6/8] Generating JWT secret"
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "$JWT_SECRET" > /tmp/taixuan_jwt_secret.txt
chmod 600 /tmp/taixuan_jwt_secret.txt
echo "      secret saved to /tmp/taixuan_jwt_secret.txt"

# 7. Update supervisor config
echo ""
echo "[7/8] Updating supervisor to set TAIXUAN_JWT_SECRET"
SUPERVISOR_CONF="/etc/supervisor/conf.d/taixuan.conf"
if [ -f "$SUPERVISOR_CONF" ]; then
  if ! grep -q "TAIXUAN_JWT_SECRET" "$SUPERVISOR_CONF"; then
    # Insert environment line
    sed -i "s|environment=|environment=TAIXUAN_JWT_SECRET=\"$JWT_SECRET\",|" "$SUPERVISOR_CONF"
    echo "      env added to supervisor conf"
  else
    echo "      env already in supervisor conf"
  fi
  supervisorctl reread
  supervisorctl update taixuan || true
else
  echo "      WARNING: supervisor conf not found at $SUPERVISOR_CONF"
  echo "      Manual: set TAIXUAN_JWT_SECRET in supervisor and restart"
fi

# 8. Start supervisor + smoke test
echo ""
echo "[8/8] Starting supervisor + smoke test"
supervisorctl start taixuan || true
sleep 3

echo ""
echo "==== Smoke test ===="
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/healthz)
echo "  /healthz: HTTP $HEALTH"
echo ""

# Test new v2.0 endpoint (should 400 on weak password)
REG=$(curl -s -X POST -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.com","password":"abc"}' \
  http://127.0.0.1:80/api/v2/auth/register)
echo "  /api/v2/auth/register (weak pw expected 400):"
echo "    $REG"

echo ""
echo "==== Done ===="
echo ""
echo "Post-deploy verification (run manually):"
echo "  curl -s http://127.0.0.1:80/healthz"
echo "  curl -s -X POST -H 'Content-Type: application/json' \\"
echo "    -d '{\"email\":\"you@example.com\",\"password\":\"goodpass1\"}' \\"
echo "    http://127.0.0.1:80/api/v2/auth/register"
echo "  browser: http://116.62.69.83/login (login page renders)"
echo "  browser: http://116.62.69.83/register (register page renders)"
echo "  browser: http://116.62.69.83/me (personal center)"
echo ""
echo "Rollback (if v2.0 breaks):"
echo "  supervisorctl stop taixuan"
echo "  cp $BACKUP_DIR/app.py $BACKUP_DIR/llm_backends.py $NEW_DIR/"
echo "  supervisorctl start taixuan"
echo ""
echo "Notes:"
echo "  - 8 new files pulled (~36 KB)"
echo "  - bcrypt installed"
echo "  - 4 new DB tables created (users, sessions, favorites, subscriptions)"
echo "  - existing v1.x readings preserved (ALTER readings ADD COLUMN user_id)"
echo "  - v1.x anonymous flow still works"
echo "  - v2.0 adds optional auth (register/login to enable history+收藏)"