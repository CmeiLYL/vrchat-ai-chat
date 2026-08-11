"""EnergyVAD：基于能量的语音活动检测（纯逻辑，无 I/O，可单测）。

流式接口：feed(块) → 返回本块触发完成的语音段列表。
把"什么时候算一句话"从触发器中独立出来，方便替换更强的 VAD
（如 silero-vad / webrtcvad），触发器代码不用动。
"""
from __future__ import annotations

import numpy as np

from vrchat_ai.infrastructure.audio_utils import rms


class EnergyVAD:
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold_db: float = -35.0,      # 语音能量阈值（dBFS）
        min_speech_s: float = 0.8,        # 最短语音段（过滤咳嗽/环境音）
        silence_timeout_s: float = 1.5,   # 静音多久判定一句话结束
        max_segment_s: float = 30.0,      # 单段上限（防无限录音）
        frame_ms: int = 50,               # 判定粒度
    ) -> None:
        self._sr = sample_rate
        self._threshold = 10 ** (threshold_db / 20)          # dBFS → 线性幅度
        self._min_speech = int(min_speech_s * sample_rate)
        self._silence_timeout = int(silence_timeout_s * sample_rate)
        self._max_segment = int(max_segment_s * sample_rate)
        self._frame = int(frame_ms * sample_rate / 1000)

        self._speech_buf = np.array([], dtype=np.float32)    # 当前语音段（只含语音帧）
        self._silence_len = 0                                 # 段尾静音累计

    # ---------- 状态机 ----------
    def feed(self, chunk: np.ndarray) -> list[np.ndarray]:
        """喂入 16kHz 单声道音频块，返回完成（结束）的语音段列表。"""
        segments: list[np.ndarray] = []
        for i in range(0, len(chunk), self._frame):
            frame = chunk[i:i + self._frame]
            if rms(frame) >= self._threshold:
                self._speech_buf = np.concatenate([self._speech_buf, frame])
                self._silence_len = 0
                if len(self._speech_buf) >= self._max_segment:
                    segments.append(self._speech_buf)
                    self._reset_buf()
            elif len(self._speech_buf) > 0:
                # 语音后的静音帧：只计时，不累积（段保持干净）
                self._silence_len += len(frame)
                if self._silence_len >= self._silence_timeout:
                    if len(self._speech_buf) >= self._min_speech:
                        segments.append(self._speech_buf)
                    self._reset_buf()
        return segments

    def flush(self) -> np.ndarray:
        """流结束时取走残留语音段（空数组表示无）。"""
        seg = self._speech_buf if len(self._speech_buf) >= self._min_speech else np.array([], dtype=np.float32)
        self._reset_buf()
        return seg

    def _reset_buf(self) -> None:
        self._speech_buf = np.array([], dtype=np.float32)
        self._silence_len = 0
