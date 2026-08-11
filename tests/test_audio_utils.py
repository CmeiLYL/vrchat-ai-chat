"""音频工具：重采样与单声道混合。"""
import numpy as np
import pytest

from vrchat_ai.infrastructure.audio_utils import resample, rms, to_mono


def test_resample_48k_to_16k_length():
    audio = np.sin(np.linspace(0, 10, 48000)).astype(np.float32)
    out = resample(audio, 48000, 16000)
    assert len(out) == 16000


def test_resample_same_rate_unchanged():
    audio = np.zeros(100, dtype=np.float32)
    assert resample(audio, 16000, 16000) is audio


def test_resample_preserves_frequency():
    """440Hz 正弦 48k→16k 后仍是 440Hz（过零率验证）。"""
    sr = 48000
    t = np.arange(sr) / sr
    audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    out = resample(audio, sr, 16000)
    crossings = np.sum(np.diff(np.sign(out)) != 0)
    freq = crossings / 2 / (len(out) / 16000)
    assert abs(freq - 440) < 5


def test_to_mono_stereo_average():
    stereo = np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32)
    mono = to_mono(stereo)
    assert np.allclose(mono, [0.3, 0.7])


def test_to_mono_mono_passthrough():
    mono = np.zeros(10, dtype=np.float32)
    assert to_mono(mono).shape == (10,)


def test_rms():
    assert rms(np.array([1.0, -1.0, 1.0, -1.0], dtype=np.float32)) == pytest.approx(1.0)
    assert rms(np.zeros(100)) == 0.0
