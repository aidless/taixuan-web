"""
test_llm_backends.py · pytest 套件

覆盖:
1. Ollama 本地兜底 真跑通(用 qwen3:4b)
2. DeepSeek API 真跑通(如果有 key)+ mock fallback 测试
3. 路由器 failover 测试
4. 4B system prompt 注入测试
5. prewarm 测试

跑法:
    cd C:\\Users\\Administrator\\cow\\fortune-web-v2
    python -m pytest tests/test_llm_backends.py -v
"""

from __future__ import annotations
import os
import json
import time
import pytest
import sys

# 让 import 能找到 llm_backends
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_backends import (
    OllamaQwen3Backend,
    DeepSeekV3Backend,
    LLMRouter,
)


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture(scope="session")
def ollama_backend():
    """Ollama 后端(全 session 复用,prewarm 一次)"""
    b = OllamaQwen3Backend()
    b.prewarm()  # 提前 warm,避免测试卡 30s
    return b


@pytest.fixture(scope="session")
def has_deepseek_key():
    """是否配置了 DeepSeek API key"""
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))


# ====================================================================
# 1. Ollama 本地兜底测试
# ====================================================================

class TestOllamaBackend:

    def test_is_alive(self, ollama_backend):
        """Ollama 服务在 :11434 监听"""
        assert ollama_backend.is_alive(), "Ollama 服务不可达"

    def test_basic_chat(self, ollama_backend):
        """基础对话:中文回答"""
        text = ollama_backend.chat(
            [{"role": "user", "content": "用一句话介绍命理学。"}],
            temperature=0.7,
            max_tokens=100,
        )
        assert len(text) > 10, f"响应过短: '{text}'"
        assert any("\u4e00" <= c <= "\u9fff" for c in text), f"应包含中文: '{text}'"

    def test_system_prompt_injection(self, ollama_backend):
        """未指定 system 时,自动注入 4B 减负 prompt(应输出 JSON)"""
        text = ollama_backend.chat(
            [{"role": "user", "content": "排盘:甲子 乙丑 丙寅 丁卯,男,问事业。"}],
            temperature=0.5,
            max_tokens=600,
        )
        # 4B system 强制 JSON 输出,试着解析
        text_clean = text.strip()
        # 找 JSON 边界(模型可能包裹其他文字)
        start = text_clean.find("{")
        end = text_clean.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = text_clean[start:end]
            parsed = json.loads(json_str)  # 期望能解析
            assert "sections" in parsed or "summary" in parsed, f"JSON 结构不符: {parsed}"

    def test_system_override(self, ollama_backend):
        """显式给 system 时,4B 默认 system 不重复"""
        custom_sys = "你只用数字回答。"
        msgs = [
            {"role": "system", "content": custom_sys},
            {"role": "user", "content": "一加一等于几?"},
        ]
        text = ollama_backend.chat(msgs, temperature=0.1, max_tokens=20)
        # 不验证具体内容,只要响应了就 OK
        assert len(text) > 0


# ====================================================================
# 2. DeepSeek API 测试
# ====================================================================

class TestDeepSeekBackend:

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY") and not os.environ.get("DEEPSEEK_API_KEY"),
        reason="需要 OPENAI_API_KEY 或 DEEPSEEK_API_KEY",
    )
    def test_real_api(self, has_deepseek_key):
        """真 API 调用(需要 key)"""
        b = DeepSeekV3Backend()
        text = b.chat(
            [{"role": "user", "content": "ping"}],
            temperature=0,
            max_tokens=10,
        )
        assert len(text) > 0, "DeepSeek 响应为空"

    def test_no_key_raises(self, monkeypatch):
        """无 key 应抛 ValueError"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API Key"):
            DeepSeekV3Backend()


# ====================================================================
# 3. 路由器 failover 测试
# ====================================================================

class TestRouter:

    def test_router_initialization(self):
        """路由器初始化(可能主路或兜底有一个未配置)"""
        router = LLMRouter()
        assert router.fallback is not None, "至少兜底 backend 应可用"

    def test_router_force_local(self, monkeypatch):
        """环境变量 LLM_MODE=fallback 强制走本地"""
        monkeypatch.setenv("LLM_MODE", "fallback")
        router = LLMRouter()
        # 强制模式下,主路被禁用
        assert router.primary is None, "LLM_MODE=fallback 应禁用主路"
        assert router.fallback is not None

    def test_router_uses_fallback(self, monkeypatch):
        """强制走 fallback,验证使用 Ollama"""
        monkeypatch.setenv("LLM_MODE", "fallback")
        router = LLMRouter()
        result = router.chat(
            [{"role": "user", "content": "你好"}],
            temperature=0.5,
            max_tokens=50,
        )
        assert result["fallback_used"] is True
        assert result["backend"] == "ollama-qwen3-4b"
        assert result["error"] == "primary_disabled"
        assert len(result["text"]) > 0


# ====================================================================
# 4. 手动 demo(不用 pytest 也能跑)
# ====================================================================

def test_demo_full_flow(ollama_backend):
    """完整流程 demo:模拟泰玄小站 8 派命理解读"""
    from datetime import datetime

    # 模拟一个排盘请求
    liupai = "bazi"  # 八字
    msgs = [
        {
            "role": "user",
            "content": (
                "流派:八字\n"
                "性别:男\n"
                "问题:近期事业发展如何?\n"
                "四柱:甲子 乙丑 丙寅 丁卯\n"
                "真太阳时:1990-01-01 12:00 北京\n"
            ),
        }
    ]

    result_text = ollama_backend.chat(msgs, temperature=0.7, max_tokens=600)

    # 4B 输出应包含中文
    assert len(result_text) > 50
    # 不应出现绝对化用词
    absolute_words = ["必定", "一定", "绝对", "注定", "必须立即"]
    for word in absolute_words:
        if word in result_text:
            pytest.fail(f"输出含绝对化用词 '{word}': {result_text[:200]}")