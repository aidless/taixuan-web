#!/bin/bash
# ECS Layer 1 健康检查 + 自动重启(cron 每 5 min)
# 部署位置:/var/www/taixuan/healthcheck.sh
# 注册:`(crontab -l 2>/dev/null; echo "*/5 * * * * /var/www/taixuan/healthcheck.sh") | crontab -`

set -u  # 不 set -e:单个检查失败不应让脚本整体退出

HEALTH_URL="http://127.0.0.1:80/healthz"
LOG_FILE="/var/log/taixuan-health.log"
MAX_LOG_SIZE_MB=10
SUPERVISOR_NAME="taixuan"

# 健康检查(超时 5s,失败码 = 5xx/连接拒绝)
HTTP_CODE=$(curl -s -o /tmp/health_body.json -w "%{http_code}" --max-time 5 "$HEALTH_URL" 2>/dev/null || echo "000")

NOW=$(date '+%Y-%m-%d %H:%M:%S')
BACKEND=$(jq -r '.primary_backend // "unknown"' /tmp/health_body.json 2>/dev/null || echo "unknown")
VERSION=$(jq -r '.version // "unknown"' /tmp/health_body.json 2>/dev/null || echo "unknown")

# 判健康:200 + status=ok
if [ "$HTTP_CODE" = "200" ]; then
    STATUS=$(jq -r '.status // "unknown"' /tmp/health_body.json 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "ok" ]; then
        echo "[$NOW] OK  http=$HTTP_CODE  backend=$BACKEND  version=$VERSION" >> "$LOG_FILE"
        exit 0
    fi
fi

# 失败路径
echo "[$NOW] FAIL  http=$HTTP_CODE  backend=$BACKEND  version=$VERSION  → restart $SUPERVISOR_NAME" >> "$LOG_FILE"

# 自动重启 supervisor 上的 taixuan
supervisorctl restart "$SUPERVISOR_NAME" >> "$LOG_FILE" 2>&1 || echo "[$NOW] supervisorctl restart failed" >> "$LOG_FILE"

# 日志轮转(超过 10MB 截断)
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE_MB=$(du -m "$LOG_FILE" 2>/dev/null | cut -f1)
    if [ "${LOG_SIZE_MB:-0}" -gt "$MAX_LOG_SIZE_MB" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        echo "[$NOW] log rotated" > "$LOG_FILE"
    fi
fi

exit 1
