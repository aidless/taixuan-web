#!/bin/bash
# 泰玄小站 · ECS 一键部署脚本
# 用法:ssh root@<YOUR_ECS_IP> 后,粘贴本脚本内容(去掉第一行的 #!/bin/bash)
# 或者先 scp 传到服务器再跑:bash deploy_ecs.sh
#
# ⚠️ 替换占位符:
#   - <YOUR_ECS_IP>  → 你的 ECS 公网 IP
#   - <YOUR_DOMAIN>   → 你的域名(可选,如 wanxiangapp.xyz)

set -e

echo "=========================================="
echo "  泰玄小站 · ECS 一键部署 (Ubuntu 22.04)"
echo "=========================================="

# ============================================================
# 1. 基础环境
# ============================================================
echo ""
echo "[1/7] 更新源 + 装基础..."
sudo apt update -qq
sudo apt install -y -qq python3-pip python3-venv nginx certbot python3-certbot-nginx rsync

# ============================================================
# 2. 创建项目目录
# ============================================================
echo ""
echo "[2/7] 创建项目目录 /var/www/taixuan..."
sudo mkdir -p /var/www/taixuan
sudo chown -R $USER:$USER /var/www/taixuan
cd /var/www/taixuan

# ============================================================
# 3. Python 虚拟环境
# ============================================================
echo ""
echo "[3/7] Python venv..."
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet flask gunicorn requests pyyaml

# ============================================================
# 4. 复制项目文件(假设你已经 scp 上来)
# ============================================================
echo ""
echo "[4/7] 项目文件部署位置 /var/www/taixuan/"
echo "  ⚠️  接下来需要你手动上传文件:"
echo "  Windows PowerShell 跑(替换占位符):"
echo ""
echo "  scp -r C:\\path\\to\\fortune-web-v2\\app.py   root@<YOUR_ECS_IP>:/var/www/taixuan/"
echo "  scp -r C:\\path\\to\\fortune-web-v2\\llm_backends.py root@<YOUR_ECS_IP>:/var/www/taixuan/"
echo "  scp -r C:\\path\\to\\fortune-web-v2\\templates root@<YOUR_ECS_IP>:/var/www/taixuan/"
echo "  scp -r C:\\path\\to\\fortune-web-v2\\static    root@<YOUR_ECS_IP>:/var/www/taixuan/"
echo "  scp -r C:\\path\\to\\fortune-web-v2\\specs     root@<YOUR_ECS_IP>:/var/www/taixuan/"
echo "  scp    C:\\path\\to\\fortune-web-v2\\requirements.txt root@<YOUR_ECS_IP>:/var/www/taixuan/"
echo ""
read -p "  文件上传完了吗?按 Enter 继续..." dummy

# ============================================================
# 5. 启动 Gunicorn (systemd)
# ============================================================
echo ""
echo "[5/7] 配置 Gunicorn systemd..."

sudo tee /etc/systemd/system/taixuan.service > /dev/null <<EOF
[Unit]
Description=Taixuan Web Flask App
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/var/www/taixuan
Environment="PATH=/var/www/taixuan/venv/bin"
ExecStart=/var/www/taixuan/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable taixuan
sudo systemctl start taixuan
sudo systemctl status taixuan --no-pager

# ============================================================
# 6. Nginx 反向代理
# ============================================================
echo ""
echo "[6/7] 配置 Nginx..."

sudo tee /etc/nginx/sites-available/taixuan > /dev/null <<'EOF'
server {
    listen 80;
    server_name <YOUR_DOMAIN> www.<YOUR_DOMAIN>;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /var/www/taixuan/static/;
        expires 7d;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/taixuan /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# ============================================================
# 7. SSL 证书(可选 · 等域名 ICP 通过后做)
# ============================================================
echo ""
echo "[7/7] SSL 证书(等域名解析生效后再跑)..."
echo "  下一步:"
echo "  1. 在阿里云 DNS 控制台,把 <YOUR_DOMAIN> 解析到 <YOUR_ECS_IP>"
echo "  2. 等 DNS 生效后(几分钟-24h),跑:"
echo "     sudo certbot --nginx -d <YOUR_DOMAIN> -d www.<YOUR_DOMAIN>"
echo ""

# ============================================================
# 完成
# ============================================================
echo ""
echo "=========================================="
echo "  ✅ 部署完成!"
echo "=========================================="
echo ""
echo "测试访问:"
echo "  本地:curl http://127.0.0.1:5000/healthz"
echo "  外部:http://<YOUR_ECS_IP> 或 http://<YOUR_DOMAIN>"
echo ""
echo "看日志:"
echo "  sudo journalctl -u taixuan -f"
echo "  tail -f /var/www/taixuan/logs/taixuan-web.log"
echo ""
echo "重启服务:"
echo "  sudo systemctl restart taixuan"