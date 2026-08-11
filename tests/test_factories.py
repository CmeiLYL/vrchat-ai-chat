"""工厂装配：按配置实例化策略。"""
import pytest

from vrchat_ai.factories import ProviderFactory
from vrchat_ai.infrastructure.console_chatbox import ConsoleChatbox
from vrchat_ai.infrastructure.llm_providers import MockProvider, OpenAICompatibleProvider
from vrchat_ai.infrastructure.osc_chatbox import OscChatbox


def test_mock_llm_factory(mock_config):
    assert isinstance(ProviderFactory(mock_config).create_llm(), MockProvider)


def test_deepseek_provider_factory(config):
    cfg = config.__class__(**{**config.__dict__, "llm_provider": "deepseek",
                              "llm_api_key": "sk-test"})
    assert isinstance(ProviderFactory(cfg).create_llm(), OpenAICompatibleProvider)


def test_console_chatbox_factory(config):
    cfg = config.__class__(**{**config.__dict__, "chatbox_channel": "console"})
    assert isinstance(ProviderFactory(cfg).create_chatbox(), ConsoleChatbox)


def test_osc_chatbox_factory(config):
    cfg = config.__class__(**{**config.__dict__, "chatbox_channel": "osc"})
    assert isinstance(ProviderFactory(cfg).create_chatbox(), OscChatbox)


def test_recognizer_shared_singleton(config):
    """识别器单例：both 模式两个通道共享同一实例（模型只加载一次）。"""
    cfg = config.__class__(**{**config.__dict__, "whisper_model": "mock"})
    factory = ProviderFactory(cfg)
    assert factory.create_recognizer() is factory.create_recognizer()


def test_unknown_provider_raises(config):
    cfg = config.__class__(**{**config.__dict__, "llm_provider": "外星模型"})
    with pytest.raises(ValueError):
        ProviderFactory(cfg).create_llm()


def test_unknown_channel_raises(config):
    cfg = config.__class__(**{**config.__dict__, "chatbox_channel": "telepathy"})
    with pytest.raises(ValueError):
        ProviderFactory(cfg).create_chatbox()
