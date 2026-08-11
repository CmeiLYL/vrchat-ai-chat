"""LLM 提供商实现：策略模式的具体策略。

- OpenAICompatibleProvider：兼容 OpenAI /chat/completions 协议，
  覆盖 DeepSeek、OpenAI、Ollama(/v1) 等一切兼容服务（同一协议，不同端点/模型）
- MockProvider：本地假实现，不联网，用于自测整条链路
"""
from __future__ import annotations

import requests

from vrchat_ai.domain.models import ChatMessage
from vrchat_ai.interfaces.llm import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """策略模式的具体策略：OpenAI 兼容协议（DeepSeek/OpenAI/Ollama 通用）。"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.9, max_tokens: int = 200, timeout: int = 120) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout

    def chat(self, messages: list[ChatMessage]) -> str:
        payload = {
            "model": self._model,
            "messages": [m.to_api_dict() for m in messages],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        resp = requests.post(self._url, json=payload, headers=self._headers, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


class MockProvider(LLMProvider):
    """策略模式的具体策略：本地假 LLM，用于自测（不联网、零成本）。

    按关键词返回固定回复，验证 输入→LLM→输出 全链路而不依赖外部服务。
    """

    def __init__(self) -> None:
        self.reply_count = 0

    def chat(self, messages: list[ChatMessage]) -> str:
        self.reply_count += 1
        # 取最近一条用户消息（历史里可能有多条）
        user_msgs = [m.content for m in messages if m.role.value == "user"]
        user_text = user_msgs[-1] if user_msgs else ""
        if "你好" in user_text or "hi" in user_text.lower():
            return "你好呀！我是小星，Mock 模式也能陪你聊天～"
        if "测试" in user_text:
            return "自测通过！这条回复来自 MockProvider，说明整条链路是通的。"
        return "嗯嗯，我在听！(Mock 回复)"
