# 部署文档

ECS 重启或者迁移到新机器时,按这个恢复。

测试过的环境:阿里云 ECS、Ubuntu 22.04、2C2G。

---

## 一句话流程

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv nginx rsync
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
mkdir -p /var/www/taixuan && cd /var/www/taixuan
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet flask gunicorn requests pyyaml

# 代码放 /var/www/taixuan/ 下,git clone 或者 scp 都行

export OPENAI_API_KEY="sk-你的key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"

# 方式 A:nohup 后台(2G 内存推荐)
nohup python -c "import os; os.environ['PORT']='80'; from app import app; app.run(host='0.0.0.0', port=80, threaded=True, debug=False)" > logs/flask.log 2>&1 &

# 方式 B:gunicorn(需要先有 swap)
gunicorn --workers 1 --bind 0.0.0.0:5000 --preload app:app
```

---

## 完整步骤

### 1. 服务器初始化

```bash
ssh root@<ECS_IP>

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx rsync curl git

# 2G 内存 ECS 必须加 swap,不然 Flask 会被 OOM killer 杀掉
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

### 2. 创建项目目录

```bash
sudo mkdir -p /var/www/taixuan
sudo chown -R $USER:$USER /var/www/taixuan
cd /var/www/taixuan

python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet flask gunicorn requests pyyaml
```

### 3. 上传代码

用 scp,从 Windows PowerShell 跑:

```powershell
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

或者用 git clone:

```bash
cd /var/www
sudo git clone https://github.com/aidless/taixuan-web.git
sudo mv taixuan-web /var/www/taixuan
cd /var/www/taixuan
```

### 4. 配置 API key

写到 systemd:

```bash
sudo mkdir -p /etc/systemd/system/taixuan.service.d
sudo tee /etc/systemd/system/taixuan.service.d/override.conf > /dev/null <<EOF
[Service]
Environment="OPENAI_API_KEY=sk-你的key"
Environment="OPENAI_API_BASE=https://api.deepseek.com/v1"
Environment="DEEPSEEK_MODEL=deepseek-v4-flash"
EOF

# 也写到 bashrc 方便调试
cat >> ~/.bashrc <<'EOF'

# DeepSeek API
export OPENAI_API_KEY="sk-你的key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"
EOF

source ~/.bashrc
```

### 5. 启动 Flask

#### 方式 A:nohup 加 Flask dev server(2G 内存 ECS 推荐)

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

curl -s http://127.0.0.1:80/healthz
```

#### 方式 B:gunicorn 加 systemd

```bash
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
Environment="OPENAI_API_KEY=sk-你的key"
Environment="OPENAI_API_BASE=https://api.deepseek.com/v1"
Environment="DEEPSEEK_MODEL=deepseek-v4-flash"
ExecStart=/var/www/taixuan/venv/bin/gunicorn --workers 1 --bind 0.0.0.0:5000 --timeout 60 --preload app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable taixuan
sudo systemctl start taixuan
sudo systemctl status taixuan --no-pager
```

可选,配 Nginx 反代(如果 Flask 直接绑 80 就跳过):

```bash
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

### 6. 验证

```bash
curl http://127.0.0.1:80/healthz
# 或 gunicorn 模式
curl http://127.0.0.1:5000/healthz

# 真实 LLM 测试
curl -X POST http://127.0.0.1:80/api/v2/liupai/bazi/reading \
  -H "Content-Type: application/json" \
  -d '{"question":"今年运势如何","birth_date":"1990-05-15","birth_time":"14:30"}'
```

### 7. 阿里云安全组放行

进 https://ecs.console.aliyun.com,实例,网络与安全,安全组,入方向,手动添加,端口 80/80,授权 0.0.0.0/0,协议 TCP。

### 8. 浏览器访问

http://<ECS_IP>

---

## 常见问题

### Flask 启动被 Killed

一般是 OOM。被 OOM killer 杀掉。

解决:

1. 加 swap,见步骤 1
2. 用 1 worker,别用 2 或 4
3. 加 --preload 共享内存
4. 关掉 Nginx,直接 Flask 绑 80,少一层

### 502 Bad Gateway

Nginx 在,但后端 Flask 没起来。

```bash
sudo ss -tlnp | grep -E ":80|:5000"  # 看哪个端口在听
sudo systemctl status taixuan
ps aux | grep -E "gunicorn|flask" | grep -v grep
```

### LLM 返回 mock 文本

backend 是 mock 而不是 deepseek-v3,说明 API key 没传给 Gunicorn。

```bash
cat /etc/systemd/system/taixuan.service.d/override.conf  # 看 key 对不对
sudo systemctl daemon-reload && sudo systemctl restart taixuan
sudo cat /proc/$(pgrep -f gunicorn | head -1)/environ | tr '\0' '\n' | grep -E OPENAI  # 看进程里有没有 key
```

### DeepSeekV3Backend 类名错误

NameError: name 'DeepSeekV3Backend' is not defined。

llm_backends.py 里要叫 DeepSeekBackend,不是 DeepSeekV3Backend。

### DeepSeek 401

HTTP Error 401: Authorization Required。

key 失效了或者模型名写错:

```bash
curl -X POST https://api.deepseek.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-你的key" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

返回 JSON 说明 key 没问题。401 就要换 key。model not found 就换成 deepseek-chat 或者 deepseek-coder。

---

## 更新代码

本地:

```powershell
cd C:\Users\Administrator\cow\fortune-web-v2
git pull
git add .
git commit -m "..."
git push origin master
```

ECS:

```bash
cd /var/www/taixuan
git pull
sudo systemctl restart taixuan  # 或 kill 老 nohup 重启
```

---

## 资源占用参考

2C2G ECS 下的实测:

- Ubuntu 22.04 加 Workbench 浏览器:大概 500MB
- Nginx:10MB
- Flask(1 worker):80MB
- DeepSeek API 调用不占内存,走外网
- 总共大概 600MB,再靠 2GB swap 顶上

并发:5 到 10 个用户每秒,Flask threaded 模式。

---

## API key 怎么存比较好

别直接写在启动命令里或者 service 文件里,日志可能泄漏。

```bash
sudo nano /etc/taixuan.env
```

写入:

```
OPENAI_API_KEY=sk-你的key
OPENAI_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-flash
```

```bash
sudo chmod 600 /etc/taixuan.env
```

然后在 service 文件里用 EnvironmentFile:

```ini
[Service]
EnvironmentFile=/etc/taixuan.env
ExecStart=/var/www/taixuan/venv/bin/gunicorn --workers 1 --bind 0.0.0.0:5000 app:app
```

---

## 日常维护

- 每周看下 logs/flask.log 找错误
- 每月跑一次 apt update 和 apt upgrade
- 每季度备份 ECS 快照
- 每年续域名和服务器

---

文档版本:v1.0 · 2026-07-12
