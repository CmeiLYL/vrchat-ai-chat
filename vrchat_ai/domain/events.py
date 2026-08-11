"""领域事件：观察者模式的载体。

事件在领域层定义，谁发布谁订阅由应用层/基础设施层决定，
领域层不知道也不关心（依赖倒置：高层不依赖低层细节）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """事件基类。"""


@dataclass(frozen=True)
class SpeechCaptured(Event):
    """语音识别完成：用户说了一句话。"""
    text: str


@dataclass(frozen=True)
class TextReceived(Event):
    """收到文字输入（预留：聊天框输入/控制台输入的扩展点）。"""
    text: str


@dataclass(frozen=True)
class ThinkingStarted(Event):
    """AI 开始思考（触发'正在输入...'气泡）。"""


@dataclass(frozen=True)
class ReplyReady(Event):
    """AI 回复就绪，可发送到任何输出通道。"""
    text: str


@dataclass(frozen=True)
class ThinkingEnded(Event):
    """AI 回复结束（收起'正在输入...'）。"""
