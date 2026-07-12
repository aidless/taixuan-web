# Dockerfile · taixuan-web
# 多阶段构建:小镜像

FROM python:3.11-slim AS runtime

# 系统依赖(用于 pyyaml)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd -m -u 1000 appuser

WORKDIR /app

# 先装依赖(利用 Docker 缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt gunicorn

# 复制应用代码
COPY app.py llm_backends.py ./
COPY templates/ ./templates/
COPY static/ ./static/
COPY specs/ ./specs/

# 日志 + 数据库目录
RUN mkdir -p /app/logs && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/healthz || exit 1

# 4 workers 生产模式
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "60", "--access-logfile", "-", "app:app"]