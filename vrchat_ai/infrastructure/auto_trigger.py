"""VoiceActivityTrigger：loopback 持续监听模式（公共 AI，无需按键）。

原理：pyaudiowpatch（PyAudio 社区分支，原生支持 WASAPI loopback）
捕获"正在播放的声音"（即 VRChat 里其他玩家的语音）→ 重采样到 16kHz
→ EnergyVAD 检测语音段 → 队列交给 worker 线程识别 → 发布事件。

回调线程只做轻量 VAD（纯 numpy），whisper 识别在独立线程，避免卡音频流。
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any

import numpy as np
import pyaudiowpatch as pyaudio

from vrchat_ai.domain.events import SpeechCaptured
from vrchat_ai.event_bus import EventBus
from vrchat_ai.infrastructure.audio_utils import resample, to_mono
from vrchat_ai.infrastructure.vad import EnergyVAD
from vrchat_ai.interfaces.speech import SpeechRecognizer
from vrchat_ai.interfaces.trigger import AudioTrigger


def select_loopback_device(candidates: list[dict], default_name: str, keyword: str = "") -> dict | None:
    """从候选 loopback 设备中选出目标（纯逻辑，可单测）。

    优先级：
    1. 指定 keyword：设备名包含关键字（如 "CABLE" → 捕获 VB-Cable 输出）
    2. 默认输出设备的同名 loopback
    3. 兜底：第一个候选
    """
    if not candidates:
        return None
    if keyword:
        for dev in candidates:
            if keyword.lower() in dev["name"].lower():
                return dev
        return None
    for dev in candidates:
        if default_name in dev["name"]:
            return dev
    return candidates[0]


def open_loopback_stream(pa, device: dict, callback) -> tuple[Any, int, int]:
    """打开 loopback 流，返回 (stream, channels, sample_rate)。

    WASAPI loopback 的通道数必须匹配源流（如 SteelSeries Sonar 是
    8ch/96kHz，只能用原生配置打开），所以优先设备原生 ch/rate；
    失败再降级尝试常见组合。
    """
    combos = [
        (int(device.get("maxInputChannels", 2)) or 2, int(device["defaultSampleRate"])),
        (2, 48000),
        (1, 48000),
    ]
    errors: list[str] = []
    for ch, rate in combos:
        try:
            stream = pa.open(
                format=pyaudio.paFloat32, channels=ch, rate=rate,
                frames_per_buffer=max(1024, int(rate * 0.1)),
                input=True, input_device_index=device["index"],
                stream_callback=callback,
            )
            return stream, ch, rate
        except Exception as exc:
            errors.append(f"{ch}ch@{rate}Hz: {exc}")
    raise RuntimeError("loopback 流打开失败: " + "; ".join(errors))


class VoiceActivityTrigger(AudioTrigger):
    """策略模式的具体策略：自动监听（WASAPI loopback + VAD）。"""

    def __init__(
        self,
        bus: EventBus,
        recognizer: SpeechRecognizer,
        sample_rate: int = 16000,
        loopback_device: str = "",          # 空=默认输出；可填关键字匹配（如 "CABLE"）
        threshold_db: float = -35.0,
        min_speech_s: float = 0.8,
        silence_timeout_s: float = 1.5,
        max_segment_s: float = 30.0,
    ) -> None:
        self._bus = bus
        self._recognizer = recognizer
        self._sample_rate = sample_rate
        self._loopback_device = loopback_device
        self._vad = EnergyVAD(
            sample_rate=sample_rate,
            threshold_db=threshold_db,
            min_speech_s=min_speech_s,
            silence_timeout_s=silence_timeout_s,
            max_segment_s=max_segment_s,
        )
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=8)
        self._src_rate = 0
        self._channels = 2
        # 回调里依赖 _src_rate/_channels，open 前占位；open 后由返回值覆盖
        self._stream = None

    # ---------- 音频回调（实时线程，必须快） ----------
    def _callback(self, in_data, frame_count, time_info, status) -> Any:
        try:
            audio = np.frombuffer(in_data, dtype=np.float32)
            if self._channels > 1:
                audio = audio.reshape(-1, self._channels)
            chunk = resample(to_mono(audio), self._src_rate, self._sample_rate)
            for seg in self._vad.feed(chunk):
                try:
                    self._queue.put_nowait(seg)
                except queue.Full:
                    pass  # 处理不过来就丢，优先实时性
        except Exception as exc:
            # 回调线程异常绝不能外泄（PortAudio 会把异常变成主线程 SystemError）
            print(f"[监听] 回调异常: {exc}")
        return None, pyaudio.paContinue

    # ---------- worker（识别线程） ----------
    def _worker(self):
        while True:
            seg = self._queue.get()
            duration = len(seg) / self._sample_rate
            print(f"[监听] 检测到语音段（{duration:.1f}s），识别中...")
            text = self._recognizer.transcribe(seg)
            if text:
                print(f"[监听] 听到: {text}")
                self._bus.publish(SpeechCaptured(text=text))
            else:
                print("[监听] 没听清，忽略")

    # ---------- 主循环 ----------
    def run(self) -> None:
        pa = pyaudio.PyAudio()
        try:
            wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_name = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])["name"]
            candidates = list(pa.get_loopback_device_info_generator())
            loopback = select_loopback_device(candidates, default_name, self._loopback_device)
            if loopback is None:
                raise RuntimeError("找不到 WASAPI loopback 设备（换驱动或检查音频设置）")
        except Exception:
            pa.terminate()
            raise

        self._src_rate = int(loopback["defaultSampleRate"])
        self._channels = max(1, int(loopback.get("maxInputChannels", 2)) or 2)
        print(f"[监听] 捕获设备: {loopback['name']} ({self._src_rate}Hz, {self._channels}ch)")
        print(f"[监听] 持续监听中：VRChat 里任何人说话都会触发 AI 回复。Ctrl+C 退出。")

        threading.Thread(target=self._worker, daemon=True).start()
        stream, self._channels, self._src_rate = open_loopback_stream(pa, loopback, self._callback)
        self._stream = stream
        try:
            stream.start_stream()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[监听] 退出。")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
