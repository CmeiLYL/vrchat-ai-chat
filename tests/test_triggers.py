"""触发策略：工厂装配与接口一致性。"""
import pytest

from vrchat_ai.factories import ProviderFactory
from vrchat_ai.infrastructure.auto_trigger import VoiceActivityTrigger, select_loopback_device
from vrchat_ai.infrastructure.hotkey_trigger import HotkeyTrigger, match_device_by_keyword
from vrchat_ai.interfaces.trigger import AudioTrigger


# ---------- 麦克风设备关键字匹配（纯逻辑） ----------
INPUT_DEVICES = [
    {"name": "SteelSeries Sonar - Microphone", "index": 10, "max_input_channels": 2},
    {"name": "EDIFIER W820NB Stereo", "index": 11, "max_input_channels": 1},
    {"name": "Voicemeeter Out B1", "index": 12, "max_input_channels": 2},
]


def test_match_by_keyword():
    dev = match_device_by_keyword(INPUT_DEVICES, "EDIFIER")
    assert dev is not None and "EDIFIER" in dev["name"]


def test_match_case_insensitive():
    dev = match_device_by_keyword(INPUT_DEVICES, "sonar")
    assert dev is not None and "Sonar" in dev["name"]


def test_match_no_keyword_returns_none():
    assert match_device_by_keyword(INPUT_DEVICES, "") is None


def test_match_no_hit_returns_none():
    assert match_device_by_keyword(INPUT_DEVICES, "外星麦克风") is None


def test_match_empty_list():
    assert match_device_by_keyword([], "EDIFIER") is None


# ---------- loopback 设备选择（纯逻辑） ----------
CANDIDATES = [
    {"name": "扬声器 (Realtek(R) Audio) [Loopback]", "index": 1},
    {"name": "CABLE Input (VB-Audio Virtual Cable) [Loopback]", "index": 2},
    {"name": "耳机 (EDIFIER) [Loopback]", "index": 3},
]


def test_select_by_keyword():
    dev = select_loopback_device(CANDIDATES, "扬声器 (Realtek(R) Audio)", "CABLE")
    assert dev is not None and "CABLE" in dev["name"]


def test_select_by_default_name():
    dev = select_loopback_device(CANDIDATES, "耳机 (EDIFIER)", "")
    assert dev is not None and "EDIFIER" in dev["name"]


def test_select_fallback_first():
    dev = select_loopback_device(CANDIDATES, "不存在的设备名", "")
    assert dev is CANDIDATES[0]


def test_select_keyword_no_match_returns_none():
    assert select_loopback_device(CANDIDATES, "扬声器", "外星设备") is None


def test_select_empty_candidates():
    assert select_loopback_device([], "任何", "") is None


def test_both_triggers_implement_interface():
    assert issubclass(HotkeyTrigger, AudioTrigger)
    assert issubclass(VoiceActivityTrigger, AudioTrigger)


def test_f8_mode_creates_hotkey_trigger(config, bus):
    cfg = config.__class__(**{**config.__dict__, "trigger_mode": "f8",
                              "whisper_model": "mock"})
    trigger = ProviderFactory(cfg).create_trigger(bus)
    assert isinstance(trigger, HotkeyTrigger)


def test_auto_mode_creates_vad_trigger(config, bus):
    cfg = config.__class__(**{**config.__dict__, "trigger_mode": "auto",
                              "whisper_model": "mock"})
    trigger = ProviderFactory(cfg).create_trigger(bus)
    assert isinstance(trigger, VoiceActivityTrigger)


def test_auto_mode_passes_loopback_device(config, bus):
    """工厂必须把 LOOPBACK_DEVICE 配置传给触发器（曾漏传导致监听错设备）。"""
    cfg = config.__class__(**{**config.__dict__, "trigger_mode": "auto",
                              "whisper_model": "mock", "loopback_device": "EDIFIER"})
    trigger = ProviderFactory(cfg).create_trigger(bus)
    assert trigger._loopback_device == "EDIFIER"  # noqa: SLF001


def test_both_mode_creates_composite(config, bus):
    """both 模式：组合触发器，内部含热键 + 自动监听两个通道。"""
    from vrchat_ai.infrastructure.composite_trigger import CompositeTrigger

    cfg = config.__class__(**{**config.__dict__, "trigger_mode": "both",
                              "whisper_model": "mock"})
    trigger = ProviderFactory(cfg).create_trigger(bus)
    assert isinstance(trigger, CompositeTrigger)
    assert len(trigger._triggers) == 2  # noqa: SLF001
    assert any(isinstance(t, HotkeyTrigger) for t in trigger._triggers)  # noqa: SLF001
    assert any(isinstance(t, VoiceActivityTrigger) for t in trigger._triggers)  # noqa: SLF001


def test_unknown_trigger_mode_raises(config, bus):
    cfg = config.__class__(**{**config.__dict__, "trigger_mode": "外星模式"})
    with pytest.raises(ValueError):
        ProviderFactory(cfg).create_trigger(bus)


def test_invalid_trigger_mode_rejected_by_validate(config):
    cfg = config.__class__(**{**config.__dict__, "trigger_mode": "外星模式"})
    problems = cfg.validate()
    assert any("TRIGGER_MODE" in p for p in problems)
