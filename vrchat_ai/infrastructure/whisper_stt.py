"""faster-whisper 语音识别实现。

transcribe 内部包含"有效性判断"：whisper 对音乐/环境音会"幻觉"出文本
（歌词/乱码），用 no_speech_prob（无语音概率）判定，高概率视为无效，
返回空串 —— 调用方无需关心，按"空=没听到"处理即可。
"""
from __future__ import annotations

import time

import numpy as np
from faster_whisper import WhisperModel

from vrchat_ai.interfaces.speech import SpeechRecognizer

# 判断阈值（纯函数，便于单测）
DEFAULT_NO_SPEECH_THRESHOLD = 0.6   # no_speech_prob 高于此值 → 视为音乐/环境音
DEFAULT_MIN_LOGPROB = -1.5          # 转写平均对数概率低于此值 → 质量差，视为幻觉


def is_valid_speech(text: str, no_speech_prob: float, avg_logprob: float,
                    no_speech_threshold: float = DEFAULT_NO_SPEECH_THRESHOLD,
                    min_logprob: float = DEFAULT_MIN_LOGPROB) -> bool:
    """有效性判断：转写出的文本是否真的是人说话。

    - 文本为空 → 无效
    - no_speech_prob 高 → whisper 认为这段没有人类语音（音乐/噪声）→ 无效
    - avg_logprob 过低 → 转写不可信（幻觉/乱码）→ 无效
    """
    if not text.strip():
        return False
    if no_speech_prob > no_speech_threshold:
        return False
    if avg_logprob < min_logprob:
        return False
    return True


class WhisperRecognizer(SpeechRecognizer):
    """策略模式的具体策略：faster-whisper（本地，离线）。"""

    def __init__(self, model_name: str, device: str = "cpu", compute_type: str = "int8",
                 language: str = "zh", sample_rate: int = 16000,
                 no_speech_threshold: float = DEFAULT_NO_SPEECH_THRESHOLD) -> None:
        print(f"[STT] 加载 whisper 模型: {model_name}（首次运行需下载）...")
        t0 = time.time()
        self._model = WhisperModel(model_name, device=device, compute_type=compute_type)
        print(f"[STT] 模型就绪，耗时 {time.time() - t0:.1f}s")
        self._language = language
        self._sample_rate = sample_rate
        self._no_speech_threshold = no_speech_threshold

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) < self._sample_rate * 0.3:  # 少于 0.3 秒视为无效
            return ""
        segments, info = self._model.transcribe(audio, language=self._language, vad_filter=True)
        # segments 是生成器只能遍历一次：单次遍历同时收集文本、置信度、无语音概率
        # 注意：no_speech_prob 在 Segment 上（TranscriptionInfo 没有这个字段）
        texts, probs, no_speech = [], [], []
        for seg in segments:
            texts.append(seg.text)
            if seg.avg_logprob is not None:
                probs.append(seg.avg_logprob)
            no_speech.append(seg.no_speech_prob)
        text = "".join(texts).strip()
        avg_logprob = sum(probs) / len(probs) if probs else 0.0
        max_no_speech = max(no_speech) if no_speech else 0.0  # 任一段无语音概率高 → 判定无效
        # 判断环节：音乐/环境音幻觉 → 返回空串（调用方按"没听到"处理）
        if not is_valid_speech(text, max_no_speech, avg_logprob,
                               self._no_speech_threshold):
            # 诊断信息：区分"没识别到"与"识别到但判定无效"
            print(f"[STT] 忽略: text={text!r} no_speech={max_no_speech:.2f} "
                  f"avg_logprob={avg_logprob:.2f}")
            return ""
        return text
