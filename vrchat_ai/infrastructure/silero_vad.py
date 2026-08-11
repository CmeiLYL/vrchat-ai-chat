"""SileroVAD：基于 Silero V5 神经网络的人声检测。

对标 kikitan-translator 的 VAD 方案（@ricky0123/vad-web + silero_vad_v5）：
- 神经网络判别"人在说话"，对音乐/环境音免疫（能量 VAD 的最大痛点）
- 参数对齐 kikitan：positive 0.25 / 静音 750ms 收尾 / 段前补 160ms

接口与 EnergyVAD 完全一致（feed → 完成段列表 / flush → 残留段），
auto_trigger 无需改动即可切换。
"""
from __future__ import annotations

import numpy as np
from silero_vad import VADIterator, load_silero_vad

_FRAME = 512  # Silero VAD 固定输入帧长（16kHz 下 32ms）


class SileroVAD:
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.25,          # 说话判定概率（kikitan positiveSpeechThreshold）
        min_silence_ms: int = 750,        # 静音多久收尾（kikitan redemption 24 帧 ≈ 768ms）
        pre_speech_pad_ms: int = 160,     # 段前补帧（kikitan preSpeechPadFrames 5 帧 ≈ 160ms）
        min_speech_s: float = 0.1,        # 最短语音段（kikitan minSpeechFrames 2 帧 ≈ 64ms）
        max_segment_s: float = 30.0,      # 单段上限（防无限录音）
        model=None,                       # 依赖注入：测试可传 mock，默认加载真实模型
    ) -> None:
        self._sr = sample_rate
        self._min_speech = int(min_speech_s * sample_rate)
        self._max_segment = int(max_segment_s * sample_rate)
        if model is None:
            model = load_silero_vad()
        self._vad = VADIterator(
            model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_silence_duration_ms=min_silence_ms,
            speech_pad_ms=pre_speech_pad_ms,
        )
        self._remainder = np.array([], dtype=np.float32)   # 跨块余数（512 对齐）
        self._buf = np.array([], dtype=np.float32)          # 当前语音段
        self._active = False                                # 是否处于说话中

    # ---------- 状态机 ----------
    def feed(self, chunk: np.ndarray) -> list[np.ndarray]:
        """喂入 16kHz 单声道音频块，返回完成（结束）的语音段列表。"""
        data = np.concatenate([self._remainder, chunk])
        usable = len(data) - len(data) % _FRAME
        frames = data[:usable].reshape(-1, _FRAME)
        self._remainder = data[usable:]

        segments: list[np.ndarray] = []
        for frame in frames:
            result = self._vad(frame) or {}   # silero-vad 6.x：无事件返回 None
            if "start" in result:
                self._active = True
                self._buf = np.array([], dtype=np.float32)
            if self._active:
                self._buf = np.concatenate([self._buf, frame])
                if len(self._buf) >= self._max_segment:
                    segments.append(self._buf[: self._max_segment])
                    self._active = False
                    self._buf = np.array([], dtype=np.float32)
            if "end" in result and self._active:
                seg = self._buf
                if len(seg) >= self._min_speech:
                    segments.append(seg)
                self._active = False
                self._buf = np.array([], dtype=np.float32)
        return segments

    def flush(self) -> np.ndarray:
        """流结束时取走残留语音段（空数组表示无）。"""
        seg = self._buf if (self._active and len(self._buf) >= self._min_speech) \
            else np.array([], dtype=np.float32)
        self._active = False
        self._buf = np.array([], dtype=np.float32)
        return seg

    def reset(self) -> None:
        """清空状态（切换监听目标/异常恢复时用）。"""
        self._active = False
        self._buf = np.array([], dtype=np.float32)
        self._remainder = np.array([], dtype=np.float32)
        self._vad.reset_states()
