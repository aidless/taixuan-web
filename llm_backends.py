"""
fortune-web-v2 · LLM Backends
统一接口的两个 LLM 后端 + 路由器(主路 DeepSeek → 兜底 Ollama qwen3)

v2.1 (2026-07-12 泰):修复 ECS 部署 bug
- 类名 DeepSeekV3Backend → DeepSeekBackend 一致
- 缺 API key 时自动 fallback 到 Ollama
- 无 key 无 ollama 时返回 mock 响应(开发用)
"""

from __future__ import annotations
import os
import json
import time
import urllib.request
import urllib.error
from typing import Protocol, List, Dict, Any, Optional, Generator


# ============================================================
# 1. LLM 后端接口契约
# ============================================================

class LLMBackend(Protocol):
    name: str
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        ...
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Generator[str, None, None]:
        """流式 chat,逐 chunk yield text 片段"""
        ...


# ============================================================
# 2. DeepSeek 后端(主路 · 在线 · OpenAI 兼容)
# ============================================================

class DeepSeekBackend:
    """DeepSeek via OpenAI-compatible API"""

    name = "deepseek-v3"

    def __init__(self):
        # 支持 OPENAI_API_KEY 或 DEEPSEEK_API_KEY(优先用 OPENAI_API_KEY 因为 DeepSeek 平台也认)
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
        self.api_base = os.environ.get("OPENAI_API_BASE", "https://api.deepseek.com/v1")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v3-flash")
        self._prewarmed = False

        if not self.api_key:
            raise ValueError(
                "DeepSeekBackend: 未设置 API Key(env: OPENAI_API_KEY 或 DEEPSEEK_API_KEY)"
            )

    def _post(self, path: str, payload: dict, stream_timeout: int = 60) -> dict:
        url = f"{self.api_base.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=stream_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        t0 = time.time()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = self._post("/chat/completions", payload)
            text = resp["choices"][0]["message"]["content"]
            elapsed = time.time() - t0
            return {
                "text": text,
                "backend": self.name,
                "fallback_used": False,
                "latency_sec": elapsed,
                "error": None,
            }
        except Exception as e:
            return {
                "text": "",
                "backend": self.name,
                "fallback_used": False,
                "latency_sec": time.time() - t0,
                "error": str(e),
            }

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Generator[str, None, None]:
        """流式 chat,逐 chunk yield text 片段。
        DeepSeek API 兼容 OpenAI stream 协议:每行 data: {json},末尾 data: [DONE]
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        url = f"{self.api_base.rstrip('/')}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if not line.startswith("data: "):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        yield text
        except Exception as e:
            yield f"[STREAM_ERROR: {e}]"

    def prewarm(self) -> None:
        if self._prewarmed:
            return
        try:
            self.chat(
                [{"role": "user", "content": "hi"}],
                max_tokens=10,
            )
            self._prewarmed = True
        except Exception:
            pass


# ============================================================
# 3. Ollama 后端(兜底 · 本地)
# ============================================================

class OllamaQwenBackend:
    """Ollama qwen3:4b 本地兜底"""

    name = "ollama-qwen3-4b"

    def __init__(self):
        self.host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
        self.num_ctx = 4096
        self._prewarmed = False

    def _post(self, path: str, payload: dict, stream_timeout: int = 180) -> dict:
        url = f"{self.host.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=stream_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        t0 = time.time()
        # qwen3 thinking 需要 num_predict 留 buffer
        num_predict = max(max_tokens + 500, 2000)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": self.num_ctx,
            },
        }
        try:
            resp = self._post("/api/chat", payload, stream_timeout=120)
            text = resp.get("message", {}).get("content", "")
            elapsed = time.time() - t0
            return {
                "text": text,
                "backend": self.name,
                "fallback_used": True,
                "latency_sec": elapsed,
                "error": None,
            }
        except Exception as e:
            return {
                "text": "",
                "backend": self.name,
                "fallback_used": True,
                "latency_sec": time.time() - t0,
                "error": str(e),
            }

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Generator[str, None, None]:
        """Ollama 流式 API,逐行返回 NDJSON"""
        num_predict = max(max_tokens + 500, 2000)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": self.num_ctx,
            },
        }
        url = f"{self.host.rstrip('/')}/api/chat"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = chunk.get("message", {}).get("content", "")
                    if text:
                        yield text
                    if chunk.get("done"):
                        break
        except Exception as e:
            yield f"[STREAM_ERROR: {e}]"

    def prewarm(self) -> None:
        if self._prewarmed:
            return
        try:
            self.chat([{"role": "user", "content": "你好"}], max_tokens=50)
            self._prewarmed = True
        except Exception:
            pass


# ============================================================
# 4. Mock 后端(开发用 · 无 API key 也能跑)
# ============================================================

class MockBackend:
    """Mock 后端 - 返回固定 fallback 文案,用于无 API key 的开发场景"""

    name = "mock"

    def __init__(self):
        self._prewarmed = True

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        time.sleep(0.5)  # 模拟延迟
        text = (
            "【开发模式 · Mock 响应】\n\n"
            "感谢你的提问。当前服务器未配置 LLM API Key,"
            "正在使用 mock 响应以保证服务可用。\n\n"
            "如需真实解读,请联系管理员配置:\n"
            "- OPENAI_API_KEY 或 DEEPSEEK_API_KEY(主路)\n"
            "- 或本地 Ollama + qwen3:4b 模型(兜底)\n\n"
            "本服务仅供文化参考与娱乐,不构成任何专业建议。"
        )
        return {
            "text": text,
            "backend": self.name,
            "fallback_used": True,
            "latency_sec": 0.5,
            "error": None,
        }

    def prewarm(self) -> None:
        pass

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Generator[str, None, None]:
        """Mock 也按字符流式 yield,模拟打字效果"""
        text = (
            "【开发模式 · Mock 响应】\n\n"
            "感谢你的提问。当前服务器未配置 LLM API Key,"
            "正在使用 mock 响应以保证服务可用。\n\n"
            "如需真实解读,请联系管理员配置:\n"
            "- OPENAI_API_KEY 或 DEEPSEEK_API_KEY(主路)\n"
            "- 或本地 Ollama + qwen3:4b 模型(兜底)\n\n"
            "本服务仅供文化参考与娱乐,不构成任何专业建议。"
        )
        # 逐字 yield,模拟打字
        for ch in text:
            yield ch
            time.sleep(0.005)


# ============================================================
# 5. 路由器(主路优先 → 兜底)
# ============================================================

class LLMRouter:
    """主路 DeepSeek → 失败 → Ollama 兜底 → 最后 Mock"""

    def __init__(
        self,
        primary: Optional[LLMBackend] = None,
        fallback: Optional[LLMBackend] = None,
        force_mode: Optional[str] = None,  # "primary" | "fallback" | "mock" | None
    ):
        force_mode = force_mode or os.environ.get("LLM_MODE")

        self.primary = primary if primary is not None else self._build_primary()
        self.fallback = fallback if fallback is not None else self._build_fallback()
        self.mock = MockBackend()
        self._primary_dead_count = 0
        self._primary_dead_threshold = 2

        if force_mode == "fallback":
            self.primary = None
        elif force_mode == "primary":
            self.fallback = None
        elif force_mode == "mock":
            self.primary = None
            self.fallback = None

    def _build_primary(self) -> Optional[LLMBackend]:
        try:
            return DeepSeekBackend()
        except Exception as e:
            print(f"[LLMRouter] primary unavailable: {e}", flush=True)
            return None

    def _build_fallback(self) -> Optional[LLMBackend]:
        try:
            return OllamaQwenBackend()
        except Exception as e:
            print(f"[LLMRouter] fallback unavailable: {e}", flush=True)
            return None

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        """主路 → 兜底 → Mock,任一成功就返回"""
        # 1. 主路
        if self.primary and self._primary_dead_count < self._primary_dead_threshold:
            result = self.primary.chat(messages, temperature, max_tokens)
            if not result.get("error") and result.get("text"):
                return result
            self._primary_dead_count += 1
            print(f"[LLMRouter] primary failed: {result.get('error')}", flush=True)
        else:
            result = {"error": "primary disabled"}

        # 2. 兜底
        if self.fallback:
            result = self.fallback.chat(messages, temperature, max_tokens)
            if not result.get("error") and result.get("text"):
                return result
            print(f"[LLMRouter] fallback failed: {result.get('error')}", flush=True)
        else:
            result = {"error": "fallback disabled"}

        # 3. Mock 兜底(无 API key 时一定走这里)
        return self.mock.chat(messages, temperature, max_tokens)

    def prewarm(self) -> None:
        if self.primary:
            try:
                self.primary.prewarm()
            except Exception:
                pass
        if self.fallback:
            try:
                self.fallback.prewarm()
            except Exception:
                pass

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> Generator[str, None, None]:
        """流式调度:主路 → 失败 → 兜底 → mock

        注意:主路失败标志是 yield [STREAM_ERROR: ...] 的 chunk
        """
        backend_used = "unknown"
        primary_failed = True

        # 1. 主路
        if self.primary and self._primary_dead_count < self._primary_dead_threshold:
            try:
                had_chunk = False
                for chunk in self.primary.chat_stream(messages, temperature, max_tokens):
                    if chunk.startswith("[STREAM_ERROR"):
                        raise RuntimeError(chunk)
                    had_chunk = True
                    yield chunk
                if had_chunk:
                    primary_failed = False
                    backend_used = self.primary.name
            except Exception as e:
                print(f"[LLMRouter] primary stream failed: {e}", flush=True)
                self._primary_dead_count += 1

        # 2. 兜底(主路失败)
        if primary_failed:
            if self.fallback:
                try:
                    had_chunk = False
                    for chunk in self.fallback.chat_stream(messages, temperature, max_tokens):
                        if chunk.startswith("[STREAM_ERROR"):
                            raise RuntimeError(chunk)
                        had_chunk = True
                        yield chunk
                    if had_chunk:
                        backend_used = self.fallback.name
                        primary_failed = False
                except Exception as e:
                    print(f"[LLMRouter] fallback stream failed: {e}", flush=True)

        # 3. Mock 兜底(都失败)
        if primary_failed:
            backend_used = self.mock.name
            for chunk in self.mock.chat_stream(messages, temperature, max_tokens):
                yield chunk


if __name__ == "__main__":
    # CLI 测试
    router = LLMRouter()
    print(f"primary: {router.primary.name if router.primary else 'None'}")
    print(f"fallback: {router.fallback.name if router.fallback else 'None'}")
    result = router.chat([
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "你好"},
    ])
    print(f"backend: {result['backend']}")
    print(f"text: {result['text'][:200]}")