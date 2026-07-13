#!/bin/bash
# 注册 ECS Layer 1 健康检查 cron(每 5 min 跑一次)
# 在 ECS Workbench 执行:`bash /var/www/taixuan/deploy_cron_healthcheck.sh`
# 注意:不是 cron 表本身需要 root,而是这个脚本要写到 /var/spool/cron/crontabs/root

SCRIPT_PATH="/var/www/taixuan/healthcheck.sh"
CRON_LINE="*/5 * * * * /bin/bash $SCRIPT_PATH >> /var/log/taixuan-cron.log 2>&1"

# 检查脚本是否存在且可执行
if [ ! -x "$SCRIPT_PATH" ]; then
    echo "ERROR: $SCRIPT_PATH 不存在或不可执行"
    echo "       请先跑:chmod +x $SCRIPT_PATH"
    exit 1
fi

# 避免重复注册
EXISTING=$(crontab -l 2>/dev/null | grep -F "healthcheck.sh" || true)
if [ -n "$EXISTING" ]; then
    echo "Cron 已经注册了:"
    echo "$EXISTING"
    exit 0
fi

# 注册
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -

echo "✅ Cron 注册成功:"
echo "  $CRON_LINE"
echo ""
echo "查看:crontab -l | grep healthcheck"
echo "日志:/var/log/taixuan-cron.log"
