# 部署文档 · Deploy Guide

> ECS 重启 / 迁移 / 重建时,按本文档恢复  
> Last verified: 2026-07-12 · 阿里云 ECS · Ubuntu 22.04 · 2C2G

---

## 🎯 一句话流程

```bash
# 1. 装基础 + 创建项目目录 + venv(一次性)
sudo apt update && sudo apt install -y python3-pip python3-venv nginx rsync
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
mkdir -p /var/www/taixuan && cd /var/www/taixuan
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet flask gunicorn requests pyyaml

# 2. 把代码放到 /var/www/taixuan/(scp 上传 或 git clone)
# (本仓库代码已在 ECS 上,跳过这步)

# 3. 设环境变量(API key)
export OPENAI_API_KEY="sk-your-deepseek-key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"

# 4. 启动(2 选 1)
# 方式 A:nohup 后台跑(轻量)
nohup python -c "import os; os.environ['PORT']='80'; from app import app; app.run(host='0.0.0.0', port=80, threaded=True, debug=False)" > logs/flask.log 2>&1 &

# 方式 B:gunicorn 生产模式(需要先有 swap 防 OOM)
gunicorn --workers 1 --bind 0.0.0.0:5000 --preload app:app
```

---

## 📋 完整部署步骤(从零开始)

### 步骤 1 · 服务器初始化

```bash
# SSH 登录
ssh root@<ECS_IP>

# 系统更新
sudo apt update && sudo apt upgrade -y

# 装基础工具
sudo apt install -y python3-pip python3-venv nginx rsync curl git

# 2G 内存 ECS 必须加 swap(防 OOM killer)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# 持久化(重启保留)
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 验证 swap
free -h
# 应该看到 Swap: 2.0Gi
```

### 步骤 2 · 创建项目目录 + Python venv

```bash
sudo mkdir -p /var/www/taixuan
sudo chown -R $USER:$USER /var/www/taixuan
cd /var/www/taixuan

python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet flask gunicorn requests pyyaml
```

### 步骤 3 · 上传代码

#### 方式 A · SCP(从 Windows 本地)

```powershell
# PowerShell 跑(替换 IP 和密码)
$env:PATH = "$env:PATH;C:\Windows\System32\OpenSSH"
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  app.py root@<ECS_IP>:/var/www/taixuan/
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  llm_backends.py root@<ECS_IP>:/var/www/taixuan/
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r `
  templates root@<ECS_IP>:/var/www/taixuan/
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r `
  static root@<ECS_IP>:/var/www/taixuan/
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r `
  specs root@<ECS_IP>:/var/www/taixuan/
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  requirements.txt root@<ECS_IP>:/var/www/taixuan/
```

#### 方式 B · Git clone(推荐,持续更新方便)

```bash
cd /var/www/www  # 或任意目录
sudo git clone https://github.com/aidless/taixuan-web.git
sudo mv taixuan-web /var/www/taixuan
cd /var/www/taixuan
```

### 步骤 4 · 配置 API key

```bash
# 写到 systemd(生产模式)
sudo mkdir -p /etc/systemd/system/taixuan.service.d
sudo tee /etc/systemd/system/taixuan.service.d/override.conf > /dev/null <<EOF
[Service]
Environment="OPENAI_API_KEY=sk-your-deepseek-key"
Environment="OPENAI_API_BASE=https://api.deepseek.com/v1"
Environment="DEEPSEEK_MODEL=deepseek-v4-flash"
EOF

# 也写到 bashrc(测试用)
cat >> ~/.bashrc <<'EOF'

# DeepSeek API
export OPENAI_API_KEY="sk-your-deepseek-key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"
EOF

source ~/.bashrc
```

### 步骤 5 · 启动 Flask(2 种方式)

#### 方式 A · nohup + Flask dev server(轻量,2G 内存 ECS 推荐)

```bash
cd /var/www/taixuan
source venv/bin/activate

mkdir -p logs

nohup python -c "
import os
os.environ['PORT'] = '80'
from app import app
app.run(host='0.0.0.0', port=80, threaded=True, debug=False)
" > logs/flask.log 2>&1 &

echo "Started PID: $!"
sleep 3

# 验证
curl -s http://127.0.0.1:80/healthz
# 应返回 {"status":"ok",...}
```

#### 方式 B · Gunicorn + systemd(生产推荐)

```bash
# 1. systemd service 文件
sudo tee /etc/systemd/system/taixuan.service > /dev/null <<'EOF'
[Unit]
Description=Taixuan Web Flask App
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/var/www/taixuan
Environment="PATH=/var/www/taixuan/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="OPENAI_API_KEY=sk-your-deepseek-key"
Environment="OPENAI_API_BASE=https://api.deepseek.com/v1"
Environment="DEEPSEEK_MODEL=deepseek-v4-flash"
ExecStart=/var/www/taixuan/venv/bin/gunicorn --workers 1 --bind 0.0.0.0:5000 --timeout 60 --preload app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 2. 启用 + 启动
sudo systemctl daemon-reload
sudo systemctl enable taixuan
sudo systemctl start taixuan
sudo systemctl status taixuan --no-pager

# 3. 配 Nginx 反代(可选,如果 Flask 直接绑 80 可跳过)
sudo tee /etc/nginx/sites-available/taixuan > /dev/null <<'EOF'
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 10M;
    
    location /static/ {
        alias /var/www/taixuan/static/;
        expires 7d;
    }
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/taixuan /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 步骤 6 · 验证

```bash
# 健康检查
curl http://127.0.0.1:80/healthz
# 或 gunicorn 模式
curl http://127.0.0.1:5000/healthz

# 真实 LLM 测试
curl -X POST http://127.0.0.1:80/api/v2/liupai/bazi/reading \
  -H "Content-Type: application/json" \
  -d '{"question":"今年运势如何","birth_date":"1990-05-15","birth_time":"14:30"}'
```

### 步骤 7 · 阿里云安全组放行

1. https://ecs.console.aliyun.com
2. 实例 → ECS 实例 → 网络与安全 → 安全组
3. 入方向 → 手动添加:
   - 端口:`80/80`
   - 授权对象:`0.0.0.0/0`
   - 协议:TCP
4. 保存

### 步骤 8 · 浏览器访问

```
http://<ECS_IP>
```

应看到 8 派卡片首页。

---

## 🔧 常见故障排除

### 故障 1 · Flask 启动被 Killed

**症状**:`Killed` 出现在 gunicorn 或 python 启动后  
**原因**:ECS 内存不够(2G),被 OOM killer 杀掉  
**修法**:
1. 加 swap(本文档步骤 1 已写)
2. 用 1 worker,不要 `--workers 2` 或 `--workers 4`
3. 加 `--preload` 共享内存
4. 不开 Nginx(直接 Flask 绑 80,少一层开销)

### 故障 2 · 502 Bad Gateway

**症状**:浏览器访问返回 502  
**原因**:Nginx 在但后端 Flask 没起来  
**修法**:
```bash
sudo ss -tlnp | grep -E ":80|:5000"  # 看哪个端口在听
sudo systemctl status taixuan
# 或
ps aux | grep -E "gunicorn|flask" | grep -v grep
```

### 故障 3 · LLM 返回 mock 文本

**症状**:`backend: mock` 而不是 `deepseek-v3`  
**原因**:API key 没传给 Gunicorn 进程  
**修法**:
1. 看 override.conf: `cat /etc/systemd/system/taixuan.service.d/override.conf`
2. 检查 key 是否正确
3. `sudo systemctl daemon-reload && sudo systemctl restart taixuan`
4. 看进程环境: `sudo cat /proc/$(pgrep -f gunicorn | head -1)/environ | tr '\0' '\n' | grep -E OPENAI`

### 故障 4 · Gunicorn DeepSeekV3Backend 类名错误

**症状**:`NameError: name 'DeepSeekV3Backend' is not defined`  
**原因**:`llm_backends.py` 类名不一致  
**修法**:确认 `llm_backends.py` 用 `class DeepSeekBackend:`,不是 `class DeepSeekV3Backend:`

### 故障 5 · DeepSeek key 401

**症状**:`HTTP Error 401: Authorization Required`  
**原因**:key 失效或模型名错  
**修法**:
```bash
# 直连测试
curl -X POST https://api.deepseek.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```
- 返回 JSON = key OK
- 401 = 换 key
- model not found = 换 `deepseek-chat` 或 `deepseek-coder`

---

## 🔁 更新代码流程

```bash
# 在本地(Windows PowerShell)
cd C:\Users\Administrator\cow\fortune-web-v2
git pull  # 拉最新
git add .
git commit -m "..."
git push origin main

# 在 ECS(Workbench)
cd /var/www/taixuan
git pull
# 或 scp 上传新文件
sudo systemctl restart taixuan  # 或 kill 老 nohup 重启
```

---

## 📊 资源占用参考(2C2G ECS)

| 组件 | 内存 |
|---|---|
| Ubuntu 22.04 + Workbench 浏览器 | ~500 MB |
| Nginx | ~10 MB |
| Flask (1 worker) | ~80 MB |
| DeepSeek API 调用 | ~0(走外网) |
| **总计** | **~600 MB** + 2GB swap |

并发能力:~5-10 个用户/秒(Flask threaded 模式)

---

## 🪤 永久保存 API key 的最佳实践

**不要** 把 key 直接写在 service 文件 / 启动命令里(可能日志泄漏)。

**推荐做法**:

```bash
# 1. 创建 secrets 文件,权限 600(只有 root 能读)
sudo nano /etc/taixuan.env
```

写入:
```
OPENAI_API_KEY=sk-your-deepseek-key
OPENAI_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-flash
```

```bash
sudo chmod 600 /etc/taixuan.env
```

修改 systemd service 用 `EnvironmentFile`:

```ini
[Service]
EnvironmentFile=/etc/taixuan.env
ExecStart=/var/www/taixuan/venv/bin/gunicorn --workers 1 --bind 0.0.0.0:5000 app:app
```

---

## 📅 定期维护

| 频率 | 操作 |
|---|---|
| 每周 | 看 logs/flask.log,检查错误 |
| 每月 | `apt update && apt upgrade -y` |
| 每季 | 备份 ECS 镜像(快照) |
| 每年 | 续费域名 + 服务器 |

---

_文档版本:v1.0 · 2026-07-12 · 作者:刘泽文_