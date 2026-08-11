"""简单工厂：按配置创建策略实例。

开闭原则：新增 LLM 提供商 / 输出通道 / 识别器时，
只需加实现类 + 在对应工厂里注册，调用方零改动。
"""
from __future__ import annotations

from vrchat_ai.infrastructure.auto_trigger import VoiceActivityTrigger
from vrchat_ai.infrastructure.composite_trigger import CompositeTrigger
from vrchat_ai.infrastructure.console_chatbox import ConsoleChatbox
from vrchat_ai.infrastructure.hotkey_trigger import HotkeyTrigger
from vrchat_ai.infrastructure.llm_providers import MockProvider, OpenAICompatibleProvider
from vrchat_ai.infrastructure.osc_chatbox import OscChatbox
from vrchat_ai.infrastructure.whisper_stt import WhisperRecognizer
from vrchat_ai.interfaces.chatbox import ChatboxSender
from vrchat_ai.interfaces.llm import LLMProvider
from vrchat_ai.interfaces.speech import SpeechRecognizer
from vrchat_ai.interfaces.trigger import AudioTrigger


class ProviderFactory:
    """按配置实例化所有策略（依赖注入的集中点）。

    识别器做单例缓存：whisper 模型是重量级资源（small 约 500MB），
    both 模式两个触发通道共享同一实例，避免重复加载。
    """

    def __init__(self, config) -> None:
        self._cfg = config
        self._recognizer: SpeechRecognizer | None = None

    # ---------- LLM ----------
    def create_llm(self) -> LLMProvider:
        if self._cfg.llm_provider == "mock":
            return MockProvider()
        if self._cfg.llm_provider in ("deepseek", "openai", "ollama"):
            return OpenAICompatibleProvider(
                base_url=self._cfg.llm_base_url,
                api_key=self._cfg.llm_api_key,
                model=self._cfg.llm_model,
                temperature=self._cfg.llm_temperature,
                max_tokens=self._cfg.llm_max_tokens,
                timeout=self._cfg.llm_timeout,
            )
        raise ValueError(f"未知 LLM 提供商: {self._cfg.llm_provider}")

    # ---------- 语音识别（单例缓存） ----------
    def create_recognizer(self) -> SpeechRecognizer:
        if self._recognizer is None:
            self._recognizer = self._build_recognizer()
        return self._recognizer

    def _build_recognizer(self) -> SpeechRecognizer:
        if self._cfg.whisper_model == "mock":
            return _MockRecognizer()
        if self._cfg.stt_engine == "edge":
            from vrchat_ai.infrastructure.edge_stt import EdgeRecognizer, to_edge_language
            return EdgeRecognizer(
                language=to_edge_language(self._cfg.whisper_language),
                sample_rate=self._cfg.sample_rate,
            )
        return WhisperRecognizer(
            model_name=self._cfg.whisper_model,
            device=self._cfg.whisper_device,
            compute_type=self._cfg.whisper_compute,
            language=self._cfg.whisper_language,
            sample_rate=self._cfg.sample_rate,
        )

    # ---------- 输出通道 ----------
    def create_chatbox(self) -> ChatboxSender:
        if self._cfg.chatbox_channel == "console":
            return ConsoleChatbox()
        if self._cfg.chatbox_channel == "osc":
            return OscChatbox(host=self._cfg.osc_host, port=self._cfg.osc_port,
                              max_len=self._cfg.chatbox_max_len)
        raise ValueError(f"未知输出通道: {self._cfg.chatbox_channel}")

    # ---------- 音频触发（策略：f8 私人 / auto 公共 / both 组合） ----------
    def create_trigger(self, bus) -> AudioTrigger:
        if self._cfg.trigger_mode == "f8":
            return self._build_hotkey(bus)
        if self._cfg.trigger_mode == "auto":
            return self._build_auto(bus)
        if self._cfg.trigger_mode == "both":
            # 组合模式：两个触发通道同时运行
            return CompositeTrigger([self._build_hotkey(bus), self._build_auto(bus)])
        raise ValueError(f"未知触发模式: {self._cfg.trigger_mode}")

    def _build_hotkey(self, bus) -> HotkeyTrigger:
        return HotkeyTrigger(bus=bus, recognizer=self.create_recognizer(),
                             hotkey=self._cfg.record_hotkey,
                             sample_rate=self._cfg.sample_rate,
                             input_device=self._cfg.input_device)

    def _build_auto(self, bus) -> VoiceActivityTrigger:
        return VoiceActivityTrigger(
            bus=bus, recognizer=self.create_recognizer(), sample_rate=self._cfg.sample_rate,
            loopback_device=self._cfg.loopback_device,
            vad_engine=self._cfg.vad_engine,
            threshold_db=self._cfg.vad_threshold_db,
            min_speech_s=self._cfg.vad_min_speech_s,
            silence_timeout_s=self._cfg.vad_silence_timeout_s,
            max_segment_s=self._cfg.vad_max_segment_s,
        )


class _MockRecognizer(SpeechRecognizer):
    """自测用：固定返回一段文本，跳过真实录音。"""

    def transcribe(self, audio) -> str:
        return "你好呀"
