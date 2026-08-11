"""接口层：所有抽象接口（ABC）。

设计原则落地：
- 依赖倒置（DIP）：高层模块只依赖这里的抽象，不依赖具体实现
- 接口隔离（ISP）：每个接口只暴露最小职责
- 里氏替换（LSP）：任何实现都能无缝替换使用方
"""
from .chatbox import ChatboxSender
from .llm import LLMProvider
from .speech import SpeechRecognizer
from .text import TextProcessor

__all__ = ["ChatboxSender", "LLMProvider", "SpeechRecognizer", "TextProcessor"]
