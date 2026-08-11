"""音频触发抽象：策略模式的抽象基类。

触发方式是可替换的策略：
- HotkeyTrigger        F8 按住说话（私人模式）
- VoiceActivityTrigger loopback 持续监听，VAD 自动触发（公共模式）

两者都发布 SpeechCaptured 事件，业务层无感知。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AudioTrigger(ABC):
    """音频输入触发器：把"听到的话"变成 SpeechCaptured 事件。"""

    @abstractmethod
    def run(self) -> None:
        """阻塞运行，直到 Ctrl+C。"""
        raise NotImplementedError
