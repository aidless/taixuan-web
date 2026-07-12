#!/bin/bash
# 泰玄小站 · ECS 一键部署脚本
# 用法:ssh root@116.62.69.83 后,粘贴本脚本内容(去掉第一行的 #!/bin/bash)
# 或者先 scp 传到服务器再跑:bash deploy_ecs.sh

set -e  # 任何错误立即退出

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
echo "  Windows PowerShell 跑:"
echo "  scp -r C:\\Users\\Administrator\\cow\\fortune-web-v2\\{app.py,llm_backends.py,requirements.txt} root@116.62.69.83:/var/www/taixuan/"
echo "  scp -r C:\\Users\\Administrator\\cow\\fortune-web-v2\\templates root@116.62.69.83:/var/www/taixuan/"
echo "  scp -r C:\\Users\\Administrator\\cow\\fortune-web-v2\\static root@116.62.69.83:/var/www/taixuan/"
echo ""
echo "  8 派 prompts YAML 复制(从 wx-miniprogram 拷一份):"
echo "  scp -r C:\\test\\2026-06-27-14-59-27\\wx-miniprogram\\specs\\prompts root@116.62.69.83:/var/www/taixuan/specs/"
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
ExecStart=/var/www/taixuan/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
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
    server_name wanxiangapp.xyz www.wanxiangapp.xyz 116.62.69.83;

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
echo "  1. 在阿里云 DNS 控制台,把 wanxiangapp.xyz 解析到 116.62.69.83"
echo "  2. 等 DNS 生效后(几分钟-24h),跑:"
echo "     sudo certbot --nginx -d wanxiangapp.xyz -d www.wanxiangapp.xyz"
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
echo "  外部:http://116.62.69.83"
echo ""
echo "看日志:"
echo "  sudo journalctl -u taixuan -f"
echo "  tail -f /var/www/taixuan/logs/taixuan-web.log"
echo ""
echo "重启服务:"
echo "  sudo systemctl restart taixuan"
echo ""
echo "下一步:"
echo "  1. 在阿里云 DNS 解析 wanxiangapp.xyz → 116.62.69.83"
echo "  2. 等 ICP 备案通过(若还在审核中)"
echo "  3. 跑 certbot 申请 SSL"
echo "  4. 浏览器访问 http://wanxiangapp.xyz"