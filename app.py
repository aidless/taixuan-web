"""
泰玄小站 · Web Flask 全栈 (v1.0 · 2026-07-12)
=============================================

从 wx-miniprogram v0.2 + 8 派 prompts 移植到独立网站
域名:wanxiangapp.xyz(已 ICP 备案)
后端 LLM:fortune-web-v2/llm_backends.LLMRouter(主路 DeepSeek → 兜底 Ollama qwen3)

路由:
  GET  /                          → 首页(8 派卡片)
  GET  /liupai/<name>             → 8 派表单页(bazi/ziwei/qimen/liuyao/meihua/tarot/western/vedic)
  POST /api/v2/liupai/<name>/reading → LLM 调用接口
  GET  /privacy                   → 隐私政策
  GET  /terms                     → 服务条款
  GET  /healthz                   → 健康检查(负载均衡用)

启动:
  python app.py                   # 开发
  gunicorn -w 4 -b 127.0.0.1:5000 app:app  # 生产
"""

import os
import sys
import json
import yaml
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort, Response, stream_with_context

# v2.0 user system (auth + favorites)
import user_system  # noqa: E402
from auth_routes import auth_bp  # noqa: E402
from favorites_routes import favorites_bp  # noqa: E402
from auth_helpers import get_optional_user  # noqa: E402

# v1.3 lightweight analytics
import analytics  # noqa: E402

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = Path(r"F:\test\2026-06-27-14-59-27\wx-miniprogram\specs\prompts")
# Linux 上 prompts 目录(部署到 ECS 时):/var/www/taixuan/specs/prompts
if not PROMPTS_DIR.exists():
    alt = BASE_DIR / "specs" / "prompts"
    if alt.exists():
        PROMPTS_DIR = alt

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ============================================================
# LLM 路由(从同目录 llm_backends 复用)
# ============================================================
sys.path.insert(0, str(BASE_DIR))
from llm_backends import LLMRouter  # noqa: E402

router = LLMRouter()

# 预热(避免首请求 30s 延迟)
try:
    router.primary.prewarm() if router.primary else None
except Exception:
    pass

# ============================================================
# Flask app
# ============================================================
# Flask 应用配置
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))

# ============================================================
# v2.0 user system bootstrap
# ============================================================
# Initialize users/sessions/favorites/subscriptions tables
user_system.init_db()
# Register auth (register/login/logout/me) + favorites blueprints
app.register_blueprint(auth_bp, url_prefix="/api/v2/auth")
app.register_blueprint(favorites_bp, url_prefix="/api/v2/favorites")
logging.info("v2.0 user system registered (auth + favorites)")

# ============================================================
# v1.3 lightweight analytics bootstrap
# ============================================================
analytics.init_analytics()
analytics.install_middleware(app)
logging.info("v1.3 analytics middleware installed")
# 生产模式不重载模板(性能 +10%)
app.config["TEMPLATES_AUTO_RELOAD"] = os.environ.get("FLASK_DEBUG", "0") == "1"
# JSON 不排序(更快)
app.config["JSON_SORT_KEYS"] = False
# 上传大小限制(防滥用)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # 64KB

# ============================================================
# 安全 headers + gzip 压缩 + 静态资源缓存
# ============================================================

@app.after_request
def add_security_headers(response):
    """每个响应加 CSP / HSTS / X-Frame 等安全 headers"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # CSP(内容安全策略):防 XSS / 数据外泄
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # 'unsafe-inline' 用于内联 JS,生产可去
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'"
    )
    # 静态资源缓存 1 小时
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    # API 不缓存
    elif request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


import gzip
import io
import threading
import time as time_module
import sqlite3
from collections import defaultdict

# 限流:每 IP 每分钟 N 次,超过返回 429
# 内存字典实现(单进程够用,gunicorn 多 worker 时用 redis)
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "10"))  # 默认每分钟 10 次
RATE_WINDOW = 60  # 秒
_rate_lock = threading.Lock()
_rate_buckets = defaultdict(list)  # ip -> [timestamp1, timestamp2, ...]


def check_rate_limit(ip: str) -> bool:
    """检查 IP 是否超限。超限返回 False"""
    with _rate_lock:
        now = time_module.time()
        # 清理窗口外的记录
        _rate_buckets[ip] = [t for t in _rate_buckets[ip] if now - t < RATE_WINDOW]
        if len(_rate_buckets[ip]) >= RATE_LIMIT:
            return False
        _rate_buckets[ip].append(now)
        return True


# ============================================================
# 历史记录(SQLite 轻量级存储,不引入 SQLAlchemy)
# ============================================================

DB_PATH = LOG_DIR / "readings.db"
_db_lock = threading.Lock()


def get_db():
    """获取 SQLite 连接(每次调用都用新连接,threading 友好)"""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化 readings 表(应用启动时调用)"""
    with _db_lock:
        conn = get_db()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    liupai TEXT NOT NULL,
                    client_ip TEXT,
                    question TEXT,
                    form_json TEXT,
                    response_text TEXT,
                    reasoning_text TEXT,
                    backend TEXT,
                    latency_sec REAL,
                    chunk_count INTEGER,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_readings_created_at
                    ON readings(created_at);
                CREATE INDEX IF NOT EXISTS idx_readings_liupai
                    ON readings(liupai);
            """)
            conn.commit()
            log.info(f"SQLite DB initialized at {DB_PATH}")
        finally:
            conn.close()


def save_reading(liupai: str, client_ip: str, form_data: dict,
                 response_text: str = "", reasoning_text: str = "",
                 backend: str = "", latency_sec: float = 0.0,
                 chunk_count: int = 0, status: str = "ok",
                 user_id: int | None = None) -> int | None:
    """保存一条解读记录到 SQLite。失败不抛异常(写入失败不影响主流程)
    v2.0: 新增 user_id,None 表示匿名用户。
    Returns: lastrowid (int) or None on failure.
    """
    try:
        with _db_lock:
            conn = get_db()
            try:
                cur = conn.execute(
                    """INSERT INTO readings
                    (liupai, client_ip, question, form_json, response_text,
                     reasoning_text, backend, latency_sec, chunk_count, status,
                     user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        liupai, client_ip,
                        form_data.get("question", "")[:500],  # 截断长问题
                        json.dumps(form_data, ensure_ascii=False)[:5000],
                        response_text[:50000],
                        reasoning_text[:30000],
                        backend,
                        latency_sec,
                        chunk_count,
                        status,
                        user_id,
                    ),
                )
                conn.commit()
                llm_audit.info(
                    f"reading saved: liupai={liupai} backend={backend} "
                    f"latency={latency_sec:.1f}s chunks={chunk_count} "
                    f"chars={len(response_text)} ip={client_ip} user_id={user_id}"
                )
                return cur.lastrowid
            finally:
                conn.close()
    except Exception as e:
        log.exception(f"failed to save reading: {e}")
        return None


@app.after_request
def gzip_response(response):
    """gzip 压缩文本响应(>1KB 才有意义)"""
    # SSE 流式不压缩(实时性重要)
    if response.mimetype == "text/event-stream":
        return response
    # 不压缩已压缩内容
    if "gzip" in (response.headers.get("Content-Encoding") or ""):
        return response
    # 只压缩文本
    if not response.mimetype.startswith(("text/", "application/json", "application/javascript")):
        return response
    # 客户端支持 gzip?
    if "gzip" not in (request.headers.get("Accept-Encoding") or ""):
        return response
    # 数据太小不压缩
    response.direct_passthrough = False
    data = response.get_data()
    if len(data) < 1024:
        return response
    # gzip 压缩
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as f:
        f.write(data)
    response.set_data(buf.getvalue())
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        # 日志轮转:单个文件最大 10MB,保留 5 个备份
        RotatingFileHandler(
            LOG_DIR / "taixuan-web.log",
            encoding="utf-8",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        ),
        # LLM 调用审计日志(单独,不轮转太频繁)
        RotatingFileHandler(
            LOG_DIR / "llm-audit.log",
            encoding="utf-8",
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=3,
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("taixuan-web")
llm_audit = logging.getLogger("taixuan-llm-audit")

# 启动时初始化 DB(log 定义之后才能调)
init_db()

# ============================================================
# 8 派配置
# ============================================================
LIUPAI_LIST = [
    {"id": "bazi",      "name": "八字",       "sub": "天干地支 · 五行生克",      "icon": "☰"},
    {"id": "ziwei",     "name": "紫微斗数",   "sub": "十四主星 · 十二宫位",      "icon": "✦"},
    {"id": "qimen",     "name": "奇门遁甲",   "sub": "九宫八卦 · 时家奇门",      "icon": "☯"},
    {"id": "liuyao",    "name": "六爻",       "sub": "三枚铜钱 · 古法起卦",      "icon": "⚊"},
    {"id": "meihua",    "name": "梅花易数",   "sub": "数字起卦 · 体用生克",      "icon": "✿"},
    {"id": "tarot",     "name": "塔罗",       "sub": "78 张神秘符号 · 心理投射", "icon": "☽"},
    {"id": "western",   "name": "西方占星",   "sub": "星盘相位 · 行星运行",      "icon": "★"},
    {"id": "vedic",     "name": "吠陀占星",   "sub": "印度古法 · 二十七宿",      "icon": "☼"},
]

LIUPAI_IDS = {p["id"] for p in LIUPAI_LIST}

# ============================================================
# 工具:加载 8 派 prompt YAML
# ============================================================
_PROMPT_CACHE = {}

def load_prompt(liupai: str) -> dict:
    """从 specs/prompts/{liupai}.yaml 加载 prompt 契约"""
    if liupai in _PROMPT_CACHE:
        return _PROMPT_CACHE[liupai]
    yaml_path = PROMPTS_DIR / f"{liupai}.yaml"
    if not yaml_path.exists():
        log.warning(f"prompt yaml not found: {yaml_path}")
        return None
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    _PROMPT_CACHE[liupai] = data
    return data


def render_pan_input(liupai: str, form_data: dict) -> str:
    """根据 pan_input.template + 用户输入,渲染排盘输入段"""
    cfg = load_prompt(liupai)
    if not cfg:
        return f"用户输入：{json.dumps(form_data, ensure_ascii=False, indent=2)}"
    template = cfg.get("pan_input", {}).get("template", "")
    if not template:
        return f"用户输入：{json.dumps(form_data, ensure_ascii=False, indent=2)}"

    # 简化渲染:支持 {key} 和 {key.subkey} 替换
    rendered = template
    for key, val in form_data.items():
        rendered = rendered.replace("{" + key + "}", str(val))
        # 处理嵌套 key
        if isinstance(val, dict):
            for subkey, subval in val.items():
                rendered = rendered.replace("{" + f"{key}.{subkey}" + "}", str(subval))
    return rendered


def build_messages(liupai: str, form_data: dict) -> list:
    """构造发给 LLM 的 messages"""
    cfg = load_prompt(liupai)
    if not cfg:
        role = "你是传统文化知识助手,基于用户输入提供文化背景知识。"
    else:
        role = cfg.get("role", "").strip()

    pan_text = render_pan_input(liupai, form_data)

    user_content = f"""{pan_text}

# 用户问题
{form_data.get('question', '(无具体问题)')}
"""

    return [
        {"role": "system", "content": role},
        {"role": "user",   "content": user_content},
    ]


# ============================================================
# 路由
# ============================================================

@app.route("/")
def index():
    return render_template("index.html", liupai_list=LIUPAI_LIST)


@app.route("/liupai/<name>")
def liupai_form(name):
    if name not in LIUPAI_IDS:
        abort(404)

    # 限流(防止恶意爬所有 8 派页面,虽然 yaml 是缓存的)
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    if not check_rate_limit(client_ip):
        return ("太多请求,稍后再试", 429)

    # v1.3 analytics: track liupai_view event
    user = get_optional_user()
    analytics.track_event(
        name="liupai_view",
        ip=client_ip,
        user_id=user["user_id"] if user else None,
        liupai=name,
    )

    cfg = load_prompt(name)
    # 提取表单字段(从 context 段)
    fields = cfg.get("context", []) if cfg else []
    # 兜底字段
    if not fields:
        fields = [
            {"key": "question", "label": "你的问题", "type": "string"},
        ]
    return render_template(
        f"liupai/{name}.html",
        liupai=name,
        liupai_name=next(p["name"] for p in LIUPAI_LIST if p["id"] == name),
        fields=fields,
    )


@app.route("/api/v2/liupai/<name>/reading", methods=["POST"])
def api_reading(name):
    if name not in LIUPAI_IDS:
        return jsonify({"error": "unknown_liupai", "liupai": name}), 404

    # 0. 限流
    client_ip = _get_client_ip()
    if not check_rate_limit(client_ip):
        return jsonify({
            "error": "rate_limited",
            "detail": f"每分钟最多 {RATE_LIMIT} 次解读,请稍后再试",
        }), 429

    # 1. 取表单数据
    if request.is_json:
        form_data = request.get_json(silent=True) or {}
    else:
        form_data = request.form.to_dict()

    if not form_data.get("question"):
        return jsonify({"error": "question_required"}), 400

    # v1.3 analytics: track form_submit event
    submitter = get_optional_user()
    analytics.track_event(
        name="form_submit",
        ip=client_ip,
        user_id=submitter["user_id"] if submitter else None,
        liupai=name,
        payload={"has_birth_date": bool(form_data.get("birth_date"))},
    )

    log.info(f"reading request: liupai={name}, keys={list(form_data.keys())}")

    # 1.5 输入校验
    err_resp, err_status = _validate_question(
        form_data.get("question", ""), client_ip, "reading"
    )
    if err_resp:
        return err_resp, err_status

    # 2. 构造 messages
    messages = build_messages(name, form_data)

    # 3. 调 LLM
    t0 = time.time()
    try:
        result = router.chat(messages, temperature=0.7, max_tokens=1500)
    except Exception as e:
        log.exception("LLM call failed")
        return jsonify({"error": "llm_call_failed", "detail": str(e)}), 500

    elapsed = time.time() - t0
    log.info(f"reading done: backend={result.get('backend')}, latency={elapsed:.1f}s, fallback={result.get('fallback_used')}")

    # 4. fallback 文案兜底
    cfg = load_prompt(name)
    fallback_text = cfg.get("disclaimer", {}).get("fallback", "") if cfg else ""

    text = result.get("text", "") or fallback_text

    # 保存到历史记录(SQLite)
    user = get_optional_user()
    reading_id = save_reading(
        liupai=name,
        client_ip=client_ip,
        form_data=form_data,
        response_text=text,
        backend=result.get("backend", "unknown"),
        latency_sec=elapsed,
        status="ok" if text else "empty",
        user_id=user["user_id"] if user else None,
    )

    return jsonify({
        "liupai": name,
        "text": text,
        "backend": result.get("backend"),
        "fallback_used": result.get("fallback_used", False),
        "latency_sec": elapsed,
        "disclaimer": fallback_text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user_id": user["user_id"] if user else None,
        "reading_id": reading_id,
    })


@app.route("/api/v2/liupai/<name>/reading_stream", methods=["POST"])
def reading_stream(name):
    """流式解读接口(SSE 协议)

    请求:POST /api/v2/liupai/<liupai>/reading_stream
    Body: JSON {question, birth_date, birth_time, ...}
    响应:text/event-stream,每行:
      data: {"type": "start", "liupai": "..."}
      data: {"type": "chunk", "text": "..."}
      data: {"type": "done", "full_text": "..."}
    """
    if name not in LIUPAI_IDS:
        return jsonify({"error": "unknown_liupai", "liupai": name}), 400

    # 0. 限流(防 LLM 滥用)
    client_ip = _get_client_ip()
    if not check_rate_limit(client_ip):
        return jsonify({
            "error": "rate_limited",
            "detail": f"每分钟最多 {RATE_LIMIT} 次解读,请稍后再试",
        }), 429

    form_data = request.get_json(force=True, silent=True) or {}

    # 0.5 输入校验
    err_resp, err_status = _validate_question(
        form_data.get("question", ""), client_ip, "stream"
    )
    if err_resp:
        return err_resp, err_status

    # 组装 messages
    try:
        messages = build_messages(name, form_data)
    except Exception as e:
        log.exception("build_messages failed")
        return jsonify({"error": "build_prompt_failed", "detail": str(e)}), 500

    cfg = load_prompt(name) or {}
    backend_used = _detect_backend_used()

    # 状态变量(generator 闭包)
    state = {"full_text": "", "reasoning_text": "", "chunk_count": 0}

    def generate():
        t0 = time.time()
        # 1. 起始事件
        yield f"data: {json.dumps({'type': 'start', 'liupai': name, 'ts': t0}, ensure_ascii=False)}\n\n"

        # 2. 流式 LLM
        for chunk in router.chat_stream(messages, temperature=0.7, max_tokens=2500):
            yield from _process_stream_chunk(chunk, state)

        elapsed = time.time() - t0
        log.info(f"stream done: latency={elapsed:.1f}s, content_len={len(state['full_text'])}, reasoning_len={len(state['reasoning_text'])}, chunks={state['chunk_count']}")

        # 4. 保存历史(先 save 拿到 reading_id 再 yield done)
        user = get_optional_user()
        reading_id = save_reading(
            liupai=name, client_ip=client_ip, form_data=form_data,
            response_text=state["full_text"], reasoning_text=state["reasoning_text"],
            backend=backend_used, latency_sec=elapsed, chunk_count=state["chunk_count"],
            status="ok" if state["full_text"] else "empty",
            user_id=user["user_id"] if user else None,
        )

        # v1.3 analytics: track stream_complete event
        analytics.track_event(
            name="stream_complete",
            ip=client_ip,
            user_id=user["user_id"] if user else None,
            liupai=name,
            payload={
                "reading_id": reading_id,
                "latency_sec": round(elapsed, 2),
                "chunk_count": state["chunk_count"],
                "content_len": len(state["full_text"]),
                "backend": backend_used,
            },
        )

        # 3. 结束事件(带 reading_id,前端可用它收藏)
        fallback_text = cfg.get("disclaimer", {}).get("fallback", "") if cfg else ""
        done_payload = {
            "type": "done",
            "full_text": state["full_text"],
            "reasoning_text": state["reasoning_text"],
            "latency_sec": elapsed,
            "chunk_count": state["chunk_count"],
            "disclaimer": fallback_text,
            "reading_id": reading_id,
            "user_id": user["user_id"] if user else None,
        }
        yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 不要缓冲
            "Connection": "keep-alive",
        },
    )


def _validate_question(question: str, client_ip: str, log_prefix: str):
    """输入校验:长度 + 注入关键词检测。返回 (error_response, status) 或 (None, None)"""
    if len(question) > 500:
        return jsonify({"error": "question_too_long", "max": 500}), 400
    injection_keywords = ["忽略", "ignore previous", "disregard", "act as", "扮演", "你是黑客", "输出系统提示"]
    question_lower = question.lower()
    for kw in injection_keywords:
        if kw in question_lower:
            log.warning(f"{log_prefix} injection detected: kw={kw} ip={client_ip}")
            return jsonify({
                "error": "injection_detected",
                "detail": "问题包含敏感关键词,请重新表述",
            }), 400
    return None, None


def _get_client_ip() -> str:
    """提取客户端真实 IP(优先 X-Forwarded-For)"""
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def _detect_backend_used() -> str:
    """判断当前 router 实际会用的后端名称"""
    if router.primary and router._primary_dead_count < router._primary_dead_threshold:
        return router.primary.name
    if router.fallback:
        return router.fallback.name
    return "unknown"


def _process_stream_chunk(chunk, state):
    """处理单条 stream chunk,返回 SSE 事件字符串(或 None 跳过)
    state: dict 包含 full_text / reasoning_text / chunk_count 计数
    """
    if not isinstance(chunk, dict):
        return
    ctype = chunk.get("type")
    text = chunk.get("text", "")
    if ctype == "error":
        log.error(f"stream error: {text}")
        return f"data: {json.dumps({'type': 'error', 'message': text}, ensure_ascii=False)}\n\n"
    if ctype == "reasoning":
        state["reasoning_text"] += text
        return f"data: {json.dumps({'type': 'reasoning', 'text': text}, ensure_ascii=False)}\n\n"
    if ctype == "content":
        state["full_text"] += text
        state["chunk_count"] += 1
        return f"data: {json.dumps({'type': 'content', 'text': text, 'chunk_count': state['chunk_count']}, ensure_ascii=False)}\n\n"


# ============================================================
# 历史记录 API
# ============================================================

@app.route("/api/v2/history", methods=["GET"])
def api_history():
    """返回最近 N 条解读记录(默认 10,最多 100)。

    v2.0 行为:
      - 匿名用户 → 看所有公开解读(user_id IS NULL 或其它)
      - 登录用户 → 只看自己(user_id = 自己)

    后续可选:?scope=public 看所有公开、?scope=mine 看自己(默认)
    """
    limit = min(int(request.args.get("limit", 10)), 100)
    liupai_filter = request.args.get("liupai")
    user = get_optional_user()
    user_id = user["user_id"] if user else None
    scope = request.args.get("scope", "mine" if user_id else "public")

    try:
        conn = get_db()
        try:
            # 决定 WHERE 子句
            if user_id and scope == "mine":
                # 登录用户:只看自己的(匿名解读不包含)
                where = "WHERE user_id = ? AND status = 'ok'"
                params = [user_id]
            elif scope == "all":
                # 看所有(管理员/调试用)
                where = "WHERE status = 'ok'"
                params = []
            else:
                # 匿名 / scope=public:只看公开的(user_id IS NULL)
                where = "WHERE user_id IS NULL AND status = 'ok'"
                params = []

            if liupai_filter:
                where += " AND liupai = ?"
                params.append(liupai_filter)

            sql = (
                "SELECT id, liupai, question, backend, latency_sec, chunk_count, "
                "       created_at, user_id "
                "FROM readings " + where + " ORDER BY id DESC LIMIT ?"
            )
            params.append(limit)
            rows = conn.execute(sql, tuple(params)).fetchall()

            return jsonify({
                "count": len(rows),
                "scope": scope,
                "user_id": user_id,
                "items": [dict(r) for r in rows],
            })
        finally:
            conn.close()
    except Exception as e:
        log.exception("history query failed")
        return jsonify({"error": "history_query_failed", "detail": str(e)}), 500


@app.route("/api/v2/history/<int:reading_id>", methods=["GET"])
def api_history_detail(reading_id: int):
    """返回某条解读的完整内容"""
    try:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM readings WHERE id = ?", (reading_id,)
            ).fetchone()
            if not row:
                return jsonify({"error": "not_found"}), 404
            d = dict(row)
            # 解析 form_json
            try:
                d["form"] = json.loads(d.pop("form_json"))
            except (KeyError, json.JSONDecodeError):
                d["form"] = {}
            return jsonify(d)
        finally:
            conn.close()
    except Exception as e:
        log.exception("history detail query failed")
        return jsonify({"error": "history_detail_failed", "detail": str(e)}), 500


@app.route("/api/v2/stats", methods=["GET"])
def api_stats():
    """返回统计信息(总调用次数 / 按派别 / 按后端)"""
    try:
        conn = get_db()
        try:
            total = conn.execute("SELECT COUNT(*) FROM readings WHERE status = 'ok'").fetchone()[0]
            by_liupai = conn.execute(
                "SELECT liupai, COUNT(*) AS count FROM readings WHERE status = 'ok' "
                "GROUP BY liupai ORDER BY count DESC"
            ).fetchall()
            by_backend = conn.execute(
                "SELECT backend, COUNT(*) AS count FROM readings WHERE status = 'ok' "
                "GROUP BY backend ORDER BY count DESC"
            ).fetchall()
            avg_latency = conn.execute(
                "SELECT AVG(latency_sec) FROM readings WHERE status = 'ok' AND latency_sec > 0"
            ).fetchone()[0] or 0
            return jsonify({
                "total_readings": total,
                "by_liupai": [dict(r) for r in by_liupai],
                "by_backend": [dict(r) for r in by_backend],
                "avg_latency_sec": round(avg_latency, 2),
            })
        finally:
            conn.close()
    except Exception as e:
        log.exception("stats query failed")
        return jsonify({"error": "stats_query_failed", "detail": str(e)}), 500


@app.route("/login")
def login_page():
    """v2.0 login page (auth_routes handles the API)."""
    return render_template("login.html")


@app.route("/register")
def register_page():
    """v2.0 register page (auth_routes handles the API)."""
    return render_template("register.html")


@app.route("/me")
def me_page():
    """v2.0 personal center (auth_routes + favorites_routes handle the API)."""
    return render_template("me.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/healthz")
def healthz():
    return jsonify({
        "status": "ok",
        "service": "taixuan-web",
        "version": "1.2.0",
        "primary_backend": "deepseek-v3",
        "fallback_backend": "ollama-qwen3-4b",
        "build_time": "2026-07-13T11:45+08:00",
        "git_commit": "c376ac3",
    })


@app.route("/api/v2/version")
def api_version():
    """轻量版版本信息(给 ECS 健康检查脚本的扩展用,不影响 healthz 兼容性)"""
    return jsonify({
        "version": "1.2.0",
        "service": "taixuan-web",
        "build_time": "2026-07-13T11:45+08:00",
    })


@app.route("/api/v2/analytics/dashboard", methods=["GET"])
def api_analytics_dashboard():
    """v1.3 lightweight analytics dashboard.
    Returns PV/UV/funnel/event counts for last N days (default 7).
    """
    try:
        days = int(request.args.get("days", 7))
        days = max(1, min(days, 90))  # clamp [1, 90]
        data = analytics.aggregate_dashboard(days)
        return jsonify(data), 200
    except Exception as e:
        log.exception("analytics dashboard failed")
        return jsonify({"error": "analytics_failed", "detail": str(e)}), 500


# ============================================================
# 错误处理
# ============================================================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found"}), 404
    if (BASE_DIR / "templates" / "404.html").exists():
        return render_template("404.html"), 404
    return "页面不存在", 404


@app.errorhandler(500)
def server_error(e):
    log.exception("500 error")
    return jsonify({"error": "internal_error", "detail": str(e)}), 500


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    log.info(f"taixuan-web 启动 · port={port} · debug={debug}")
    app.run(host="0.0.0.0", port=port, debug=debug)