"""音频工具：重采样等纯函数（无 I/O，方便测试）。"""
from __future__ import annotations

import numpy as np


def resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """线性插值重采样到目标采样率（float32 单声道）。

    WASAPI loopback 通常 48kHz，whisper 需要 16kHz。
    """
    if src_rate == dst_rate:
        return audio
    if len(audio) == 0:
        return audio
    n_out = int(round(len(audio) * dst_rate / src_rate))
    x_old = np.linspace(0.0, 1.0, len(audio))
    x_new = np.linspace(0.0, 1.0, n_out)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def to_mono(audio: np.ndarray) -> np.ndarray:
    """多声道 → 单声道（均值混合）。已是单声道则原样返回。"""
    if audio.ndim == 1:
        return audio.astype(np.float32, copy=False)
    return audio.mean(axis=1).astype(np.float32)


def rms(audio: np.ndarray) -> float:
    """均方根能量（线性幅度）。"""
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio**2)))
