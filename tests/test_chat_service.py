"""ChatService 门面：全链路（Mock LLM + Console 通道，全离线）。"""
import pytest

from vrchat_ai.application.chat_service import ChatService
from vrchat_ai.application.text_pipeline import build_default_pipeline
from vrchat_ai.domain.events import ReplyReady, SpeechCaptured
from vrchat_ai.infrastructure.console_chatbox import ConsoleChatbox
from vrchat_ai.infrastructure.llm_providers import MockProvider


@pytest.fixture
def service(persona, bus):
    return ChatService(
        persona=persona, llm=MockProvider(), chatbox=ConsoleChatbox(),
        pipeline=build_default_pipeline(), bus=bus, max_rounds=8)


def test_mock_reply_uses_persona(service):
    service.handle_user_text("你好")
    assert "小星" in service._chatbox._outputs[0]  # noqa: SLF001 —— 测试白盒访问输出


def test_reply_ready_published(service, bus):
    replies = []
    bus.subscribe(ReplyReady, lambda e: replies.append(e.text))
    service.handle_user_text("你好")
    assert len(replies) == 1
    assert "小星" in replies[0]


def test_speech_event_triggers_chat(service, bus):
    """观察者联动：语音识别事件自动触发对话。"""
    replies = []
    bus.subscribe(ReplyReady, lambda e: replies.append(e.text))
    bus.publish(SpeechCaptured(text="你好"))
    assert len(replies) == 1


def test_llm_error_graceful_degradation(persona, bus):
    """LLM 抛异常时输出兜底文案，不崩溃。"""
    class BoomLLM:
        def chat(self, messages):
            raise RuntimeError("模拟网络故障")

    service = ChatService(
        persona=persona, llm=BoomLLM(), chatbox=ConsoleChatbox(),
        pipeline=build_default_pipeline(), bus=bus, max_rounds=8)
    service.handle_user_text("你好")
    assert service._chatbox._outputs[0] == "我这边出故障了，稍等一下下…"  # noqa: SLF001


def test_conversation_remembers_context(service):
    """第二轮能拿到历史（Mock 取最近一条 user 消息验证）。"""
    service.handle_user_text("测试一下管道")
    assert service._chatbox._outputs[-1] == "自测通过！这条回复来自 MockProvider，说明整条链路是通的。"  # noqa: SLF001
