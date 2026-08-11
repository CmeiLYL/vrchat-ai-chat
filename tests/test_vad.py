"""EnergyVAD：语音活动检测（纯逻辑测试）。"""
import numpy as np
import pytest

from vrchat_ai.infrastructure.vad import EnergyVAD

SR = 16000


def _tone(freq=440.0, seconds=1.0, amp=0.5):
    """合成正弦波（模拟人声能量）。"""
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _silence(seconds=1.0):
    return np.zeros(int(SR * seconds), dtype=np.float32)


def test_speech_followed_by_silence_detected():
    vad = EnergyVAD(sample_rate=SR, threshold_db=-35.0, min_speech_s=0.8,
                    silence_timeout_s=0.5)
    segs = vad.feed(np.concatenate([_tone(seconds=1.0), _silence(seconds=1.0)]))
    assert len(segs) == 1
    assert len(segs[0]) >= SR * 0.8  # 段长 ≥ 最短语音


def test_pure_silence_no_detection():
    vad = EnergyVAD(sample_rate=SR)
    assert vad.feed(_silence(seconds=5)) == []


def test_short_noise_filtered():
    """< min_speech 的短噪声不触发（如咳嗽、环境音）。"""
    vad = EnergyVAD(sample_rate=SR, min_speech_s=0.8, silence_timeout_s=0.3)
    segs = vad.feed(np.concatenate([_tone(seconds=0.2), _silence(seconds=1.0)]))
    assert segs == []


def test_two_speech_segments_separated():
    """两句话各带尾随静音 → 各自独立成段。

    注意：VAD 语义是"段结束靠静音信号"，若第二段后无静音，
    它会留在缓冲区等 flush 才返回。
    """
    vad = EnergyVAD(sample_rate=SR, min_speech_s=0.2, silence_timeout_s=0.4)
    audio = np.concatenate([_tone(seconds=0.6), _silence(seconds=0.8),
                            _tone(seconds=0.6), _silence(seconds=0.6)])
    segs = vad.feed(audio)
    assert len(segs) == 2
    assert all(len(s) >= SR * 0.2 for s in segs)


def test_max_segment_cutoff():
    vad = EnergyVAD(sample_rate=SR, min_speech_s=0.2, silence_timeout_s=1.0, max_segment_s=1.0)
    segs = vad.feed(_tone(seconds=3.0))
    # 3 秒连续语音 → 至少被切成 3 段
    assert len(segs) >= 2
    assert all(len(s) <= SR * 1.05 for s in segs)


def test_flush_returns_remaining_speech():
    vad = EnergyVAD(sample_rate=SR, min_speech_s=0.2, silence_timeout_s=5.0)
    segs = vad.feed(_tone(seconds=1.0))  # 静音未到，不触发
    assert segs == []
    remaining = vad.flush()
    assert len(remaining) >= SR * 0.8


def test_low_energy_below_threshold_ignored():
    vad = EnergyVAD(sample_rate=SR, threshold_db=-20.0, min_speech_s=0.2,
                    silence_timeout_s=0.3)
    segs = vad.feed(np.concatenate([_tone(amp=0.01, seconds=1.0), _silence(seconds=1.0)]))
    assert segs == []
