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
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort

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
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "taixuan-web.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("taixuan-web")

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

    # 1. 取表单数据
    if request.is_json:
        form_data = request.get_json(silent=True) or {}
    else:
        form_data = request.form.to_dict()

    if not form_data.get("question"):
        return jsonify({"error": "question_required"}), 400

    log.info(f"reading request: liupai={name}, keys={list(form_data.keys())}")

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
    fallback_text = ""
    if cfg and "disclaimer" in cfg:
        fallback_text = cfg["disclaimer"].get("fallback", "")

    text = result.get("text", "") or fallback_text

    return jsonify({
        "liupai": name,
        "text": text,
        "backend": result.get("backend"),
        "fallback_used": result.get("fallback_used", False),
        "latency_sec": elapsed,
        "disclaimer": fallback_text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


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
        "version": "1.0.0",
        "primary_backend": "deepseek-v3",
        "fallback_backend": "ollama-qwen3-4b",
    })


# ============================================================
# 错误处理
# ============================================================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found"}), 404
    return render_template("404.html"), 404 if (BASE_DIR / "templates" / "404.html").exists() else ("页面不存在", 404)


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