"""配置：dataclass 集中管理，.env 覆盖敏感项。

单一职责：只负责配置的加载与校验，不含任何业务逻辑。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

PERSONAS_DIR = BASE_DIR / "personas"


@dataclass(frozen=True)
class AppConfig:
    # ---------- VRChat OSC ----------
    osc_host: str = "127.0.0.1"
    osc_port: int = 9000
    chatbox_max_len: int = 144          # VRChat 聊天框单条字数上限
    chatbox_channel: str = "osc"        # osc / console（调试）

    # ---------- 语音识别 ----------
    whisper_model: str = "small"        # tiny/base/small/medium/mock
    stt_engine: str = "whisper"         # whisper=本地 faster-whisper / edge=微软云端(精度高,需网络)
    whisper_device: str = "cpu"         # cpu / cuda
    whisper_compute: str = "int8"
    whisper_language: str = "zh"
    sample_rate: int = 16000
    record_hotkey: str = "f8"
    trigger_mode: str = "both"          # f8=按住说话 / auto=loopback监听 / both=两者同时(默认)
    input_device: str = ""              # f8: 麦克风设备关键字(空=默认输入, 如 "EDIFIER")
    loopback_device: str = ""           # auto: 捕获设备关键字(空=默认输出, 如 "CABLE")
    vad_engine: str = "energy"          # energy=能量VAD / silero=神经网络VAD(抗音乐,对标kikitan)
    vad_threshold_db: float = -35.0     # 自动监听：语音能量阈值(dBFS)
    vad_min_speech_s: float = 0.8       # 自动监听：最短语音段
    vad_silence_timeout_s: float = 1.5  # 自动监听：静音多久算一句话结束
    vad_max_segment_s: float = 30.0     # 自动监听：单段上限

    # ---------- LLM ----------
    llm_provider: str = "deepseek"      # deepseek / openai / ollama / mock
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.9
    llm_max_tokens: int = 200
    llm_timeout: int = 120

    # ---------- 会话 ----------
    max_rounds: int = 8                 # 记忆最近几轮
    persona: str = ""                   # 角色卡名，空=用第一个

    # ---------- 校验 ----------
    def validate(self) -> list[str]:
        """返回配置问题列表（空 = 配置 OK）。"""
        problems: list[str] = []
        if self.llm_provider == "ollama":
            if not self.llm_base_url.startswith("http"):
                problems.append("ollama 需要配置 LLM_BASE_URL，如 http://192.168.123.71:11434/v1")
        elif self.llm_provider != "mock" and not self.llm_api_key:
            problems.append("未配置 LLM_API_KEY（复制 .env.example 为 .env 并填入）")
        if self.chatbox_channel == "osc" and self.osc_port <= 0:
            problems.append("OSC 端口无效")
        if self.trigger_mode not in ("f8", "auto", "both"):
            problems.append(f"TRIGGER_MODE 无效: {self.trigger_mode}（应为 f8 / auto / both）")
        if self.vad_engine not in ("energy", "silero"):
            problems.append(f"VAD_ENGINE 无效: {self.vad_engine}（应为 energy / silero）")
        if self.stt_engine not in ("whisper", "edge"):
            problems.append(f"STT_ENGINE 无效: {self.stt_engine}（应为 whisper / edge）")
        return problems


def load_config() -> AppConfig:
    """从环境变量 / .env 构建配置（值转换容错）。"""

    def _int(key: str, default: int) -> int:
        try:
            return int(os.getenv(key, default))
        except ValueError:
            return default

    def _float(key: str, default: float) -> float:
        try:
            return float(os.getenv(key, default))
        except ValueError:
            return default

    return AppConfig(
        osc_host=os.getenv("OSC_HOST", "127.0.0.1"),
        osc_port=_int("OSC_PORT", 9000),
        chatbox_max_len=_int("CHATBOX_MAX_LEN", 144),
        chatbox_channel=os.getenv("CHATBOX_CHANNEL", "osc"),
        whisper_model=os.getenv("WHISPER_MODEL", "small"),
        stt_engine=os.getenv("STT_ENGINE", "whisper"),
        whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
        whisper_compute=os.getenv("WHISPER_COMPUTE", "int8"),
        whisper_language=os.getenv("WHISPER_LANGUAGE", "zh"),
        sample_rate=_int("SAMPLE_RATE", 16000),
        record_hotkey=os.getenv("RECORD_HOTKEY", "f8"),
        trigger_mode=os.getenv("TRIGGER_MODE", "both"),
        input_device=os.getenv("INPUT_DEVICE", ""),
        loopback_device=os.getenv("LOOPBACK_DEVICE", ""),
        vad_engine=os.getenv("VAD_ENGINE", "energy"),
        vad_threshold_db=_float("VAD_THRESHOLD_DB", -35.0),
        vad_min_speech_s=_float("VAD_MIN_SPEECH_S", 0.8),
        vad_silence_timeout_s=_float("VAD_SILENCE_TIMEOUT_S", 1.5),
        vad_max_segment_s=_float("VAD_MAX_SEGMENT_S", 30.0),
        llm_provider=os.getenv("LLM_PROVIDER", "deepseek"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        llm_model=os.getenv("LLM_MODEL", "deepseek-chat"),
        llm_temperature=_float("LLM_TEMPERATURE", 0.9),
        llm_max_tokens=_int("LLM_MAX_TOKENS", 200),
        llm_timeout=_int("LLM_TIMEOUT", 120),
        max_rounds=_int("MAX_ROUNDS", 8),
        persona=os.getenv("PERSONA", ""),
    )
