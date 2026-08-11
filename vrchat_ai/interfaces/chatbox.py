"""聊天框输出通道抽象：策略模式的抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ChatboxSender(ABC):
    """把文字显示到目标通道（VRChat OSC 聊天框 / 控制台 / 未来 TTS...）。"""

    @abstractmethod
    def send(self, text: str) -> None:
        """发送一条文本。"""
        raise NotImplementedError

    @abstractmethod
    def typing(self, on: bool) -> None:
        """显示/取消'正在输入...'状态。"""
        raise NotImplementedError
