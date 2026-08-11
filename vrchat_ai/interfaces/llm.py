"""LLM 提供商抽象：策略模式的抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from vrchat_ai.domain.models import ChatMessage


class LLMProvider(ABC):
    """大语言模型提供商（DeepSeek / OpenAI / Ollama / Mock...）。"""

    @abstractmethod
    def chat(self, messages: list[ChatMessage]) -> str:
        """传入完整消息列表（含 system），返回 AI 回复文本。"""
        raise NotImplementedError
