"""EdgeRecognizer：协议单元测试 + 真实端点集成测试。

集成测试依赖网络（speech.platform.bing.com）与音频夹具
tests/assets/speech_sample.pcm（48kHz PCM16 中文语音，SAPI 合成）。
"""
import struct

import numpy as np
import pytest

from vrchat_ai.infrastructure.audio_utils import resample
from vrchat_ai.infrastructure.edge_stt import (
    EdgeRecognizer, _wav_header, parse_server_msg, sec_ms_gec, to_edge_language,
)

ASSET = __import__("pathlib").Path(__file__).parent / "assets" / "speech_sample.pcm"


# ---------- 协议单元 ----------
def test_sec_ms_gec_format():
    gec = sec_ms_gec()
    assert len(gec) == 64
    assert all(c in "0123456789ABCDEF" for c in gec)


def test_sec_ms_gec_stable_within_window():
    """300s 窗口内签名应稳定（服务器按窗口校验）。"""
    assert sec_ms_gec() == sec_ms_gec()


def test_wav_header_structure():
    h = _wav_header(48000)
    assert h[:4] == b"RIFF"
    assert h[8:12] == b"WAVE"
    assert h[12:16] == b"fmt "
    # fmt 块: 格式=1(PCM), 声道=1, 采样率=48000
    fmt = struct.unpack("<HHIIHH", h[20:36])
    assert fmt == (1, 1, 48000, 96000, 2, 16)


def test_parse_text_message():
    raw = "X-Timestamp:2026-01-01T00:00:00Z\r\nPath:speech.phrase\r\n\r\n{\"DisplayText\":\"你好\"}"
    path, body = parse_server_msg(raw)
    assert path == "speech.phrase"
    assert '"DisplayText"' in body


def test_parse_binary_message():
    header = "X-Timestamp:x\r\nPath:turn.start\r\nX-RequestId:abc\r\n\r\n{}"
    h = header.encode()
    raw = struct.pack(">H", len(h)) + h
    path, body = parse_server_msg(raw)
    assert path == "turn.start"


def test_to_edge_language():
    assert to_edge_language("zh") == "zh-CN"
    assert to_edge_language("en") == "en-US"
    assert to_edge_language("ja") == "ja-JP"
    assert to_edge_language("fr") == "fr-FR"
    assert to_edge_language("xx") == "xx"  # 未知透传


def test_transcribe_short_audio_returns_empty():
    rec = EdgeRecognizer()
    assert rec.transcribe(np.zeros(1600, dtype=np.float32)) == ""


# ---------- 集成测试（真实端点，需网络） ----------
@pytest.mark.integration
def test_edge_recognizer_real_chinese():
    """真实端点：识别中文语音夹具，应返回正确文本。"""
    if not ASSET.exists():
        pytest.skip("缺少音频夹具 tests/assets/speech_sample.pcm")
    pcm48 = np.fromfile(ASSET, dtype=np.int16).astype(np.float32) / 32767.0
    audio16 = resample(pcm48, 48000, 16000)  # EdgeRecognizer 输入 16k
    rec = EdgeRecognizer(language="zh-CN")
    text = rec.transcribe(audio16)
    assert text, "端点应返回识别文本"
    assert "你好" in text, f"应识别出'你好'，实际: {text!r}"


@pytest.mark.integration
def test_edge_recognizer_silence_returns_empty():
    """真实端点：静音输入应返回空（服务端 VAD 生效）。"""
    rec = EdgeRecognizer(language="zh-CN")
    text = rec.transcribe(np.zeros(16000, dtype=np.float32))  # 1s 静音
    assert text == ""
