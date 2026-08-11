"""ChatService：门面模式 + 观察者模式的订阅端。

对外只暴露 handle_user_text() 一个入口（门面），
内部串联：人设 → 会话历史 → LLM → 文本管道 → 输出通道。
同时订阅事件总线：语音识别完成的事件自动触发对话。
"""
from __future__ import annotations

import datetime
from pathlib import Path

from vrchat_ai.domain.events import ReplyReady, SpeechCaptured, ThinkingEnded, ThinkingStarted
from vrchat_ai.domain.models import Conversation, Persona, Role
from vrchat_ai.event_bus import EventBus
from vrchat_ai.interfaces.chatbox import ChatboxSender
from vrchat_ai.interfaces.llm import LLMProvider
from vrchat_ai.interfaces.text import TextProcessor

# 对话日志：每轮 [你]/[AI] 持久化，方便查看完整对话（UTF-8）
LOG_FILE = Path(__file__).resolve().parent.parent / "chat.log"


def _log(line: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%H:%M:%S}] {line}\n")
    except OSError:
        pass  # 日志写失败不影响主流程


class ChatService:
    """门面：调用方只需要这一个对象，内部编排全部隐藏。"""

    def __init__(self, persona: Persona, llm: LLMProvider, chatbox: ChatboxSender,
                 pipeline: TextProcessor, bus: EventBus, max_rounds: int = 8) -> None:
        self._persona = persona
        self._llm = llm
        self._chatbox = chatbox
        self._pipeline = pipeline
        self._bus = bus
        self._conversation = Conversation(system_prompt=persona.render_system_prompt(),
                                          max_rounds=max_rounds)
        # 观察者：订阅语音事件
        self._bus.subscribe(SpeechCaptured, self._on_speech)

    @property
    def bus(self) -> EventBus:
        """对外暴露事件总线，供发布者（如热键触发）使用。"""
        return self._bus

    # ---------- 对外入口 ----------
    def handle_user_text(self, user_text: str) -> None:
        """用户说了一句话 → 完整对话流程。"""
        print(f"[你] {user_text}")
        _log(f"[你] {user_text}")
        self._bus.publish(ThinkingStarted())

        try:
            self._conversation.add(Role.USER, user_text)
            print("[AI] 思考中...")
            reply = self._llm.chat(self._conversation.to_api_messages())
            self._conversation.add(Role.ASSISTANT, reply)

            # 责任链：清洗 → 表情 → 分段
            for chunk in self._pipeline.process_chain(reply):
                self._chatbox.send(chunk)
                self._bus.publish(ReplyReady(text=chunk))
            print(f"[AI] {reply}")
            _log(f"[AI] {reply}")
        except Exception as exc:
            print(f"[AI] 出错: {exc}")
            self._chatbox.send("我这边出故障了，稍等一下下…")
        finally:
            self._bus.publish(ThinkingEnded())

    # ---------- 观察者回调 ----------
    def _on_speech(self, event: SpeechCaptured) -> None:
        self.handle_user_text(event.text)

    # ---------- 人设 ----------
    @property
    def persona(self) -> Persona:
        return self._persona
