"""pytest 共享 fixtures。"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

# 保证 import config / vrchat_ai 可用（项目根加入 sys.path）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import PERSONAS_DIR, AppConfig, load_config  # noqa: E402
from vrchat_ai.application.persona_manager import PersonaManager  # noqa: E402
from vrchat_ai.event_bus import EventBus  # noqa: E402


@pytest.fixture
def config() -> AppConfig:
    return load_config()


@pytest.fixture
def mock_config(config: AppConfig) -> AppConfig:
    """全 Mock 配置：不联网、无硬件依赖。"""
    return config.__class__(
        **{**config.__dict__, "llm_provider": "mock", "chatbox_channel": "console",
           "whisper_model": "mock"})


@pytest.fixture
def persona() -> "Persona":
    return PersonaManager(PERSONAS_DIR).load("xiaoxing")


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def udp_port() -> int:
    """找一个空闲 UDP 端口（避免与真实 VRChat 9000 冲突）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
