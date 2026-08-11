"""控制台聊天框实现：没有 VRChat 时用于调试/自测。"""
from __future__ import annotations

from vrchat_ai.interfaces.chatbox import ChatboxSender


class ConsoleChatbox(ChatboxSender):
    """策略模式的具体策略：把回复打印到控制台（调试通道）。"""

    def __init__(self) -> None:
        self._outputs: list[str] = []

    def typing(self, on: bool) -> None:
        pass  # 控制台无需显示输入状态

    def send(self, text: str) -> None:
        print(f"[ConsoleChatbox] {text}")
        self._outputs.append(text)
