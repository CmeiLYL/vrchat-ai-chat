"""语音识别抽象：策略模式的抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class SpeechRecognizer(ABC):
    """语音识别器（faster-whisper / Mock...）。"""

    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> str:
        """把 16kHz 单声道 float32 音频转成文本。"""
        raise NotImplementedError
