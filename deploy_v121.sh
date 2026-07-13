#!/bin/bash
# v1.2.0 → v1.2.1 一键升级脚本(ECS Workbench 跑)
# 触发:app.py + healthcheck.sh + deploy_cron_healthcheck.sh 推到 GitHub 后
# 用法:bash /var/www/taixuan/deploy_v121.sh

set -e

BACKUP_DIR="/tmp/taixuan-backup-v12"
NEW_DIR="/var/www/taixuan"
BASE_URL="https://raw.githubusercontent.com/aidless/taixuan-web/main"

echo "==== v1.2.0 → v1.2.1 升级开始(7/13 12:00)===="

# 1. 备份 v1.2.0
echo "[1/6] 备份 v1.2.0 → $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
cp -f "$NEW_DIR/app.py" "$NEW_DIR/healthcheck.sh" "$BACKUP_DIR/" 2>/dev/null || true

# 2. 下载 v1.2.1 文件
echo "[2/6] 下载 v1.2.1 app.py"
curl -sSL --fail "$BASE_URL/app.py" -o "$NEW_DIR/app.py"
echo "       下载 healthcheck.sh"
curl -sSL --fail "$BASE_URL/healthcheck.sh" -o "$NEW_DIR/healthcheck.sh"
echo "       下载 deploy_cron_healthcheck.sh"
curl -sSL --fail "$BASE_URL/deploy_cron_healthcheck.sh" -o "$NEW_DIR/deploy_cron_healthcheck.sh"

# 3. 加执行权限
echo "[3/6] chmod +x"
chmod +x "$NEW_DIR/healthcheck.sh" "$NEW_DIR/deploy_cron_healthcheck.sh"

# 4. 重启 supervisor
echo "[4/6] supervisorctl restart taixuan"
supervisorctl restart taixuan

# 5. 注册 cron(幂等)
echo "[5/6] 注册 cron"
bash "$NEW_DIR/deploy_cron_healthcheck.sh"

# 6. 验证
echo "[6/6] 验证 5 条"
sleep 2
echo "--- supervisor status ---"
supervisorctl status taixuan
echo "--- /healthz ---"
curl -s http://127.0.0.1:80/healthz
echo ""
echo "--- /api/v2/version ---"
curl -s http://127.0.0.1:80/api/v2/version
echo ""
echo "--- cron 表 ---"
crontab -l | grep healthcheck || echo "(no cron yet)"
echo ""
echo "==== ✅ v1.2.0 → v1.2.1 升级完成 ===="
echo "备份:$BACKUP_DIR"
echo "日志:/var/log/taixuan-health.log(健康检查) + /var/log/taixuan-cron.log(cron 输出)"
