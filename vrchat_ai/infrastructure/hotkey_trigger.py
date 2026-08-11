"""HotkeyTrigger：F8 按住说话模式（私人模式）。

保留按键触发，与 VoiceActivityTrigger 一样实现 AudioTrigger 接口，
通过 config 的 TRIGGER_MODE 切换。
"""
from __future__ import annotations

import threading
import time

import numpy as np
import sounddevice as sd

from vrchat_ai.domain.events import SpeechCaptured
from vrchat_ai.event_bus import EventBus
from vrchat_ai.interfaces.speech import SpeechRecognizer
from vrchat_ai.interfaces.trigger import AudioTrigger


def match_device_by_keyword(devices: list[dict], keyword: str) -> dict | None:
    """按设备名关键字匹配（纯逻辑，可单测）。"""
    if not keyword:
        return None
    for dev in devices:
        if keyword.lower() in dev["name"].lower():
            return dev
    return None


class HotkeyTrigger(AudioTrigger):
    """策略模式的具体策略：热键触发（按住录音，松开发送）。"""

    def __init__(self, bus: EventBus, recognizer: SpeechRecognizer,
                 hotkey: str = "f8", sample_rate: int = 16000,
                 input_device: str = "") -> None:
        self._bus = bus
        self._recognizer = recognizer
        self._hotkey = hotkey
        self._sample_rate = sample_rate
        self._input_device = input_device  # 设备名关键字，空=默认输入
        self._chunks: list[np.ndarray] = []
        self._recording = False
        self._stream: sd.InputStream | None = None

    # ---------- 录音控制 ----------
    def _audio_callback(self, indata, frames, time_info, status):
        if self._recording:
            self._chunks.append(indata[:, 0].copy())

    def _start(self):
        self._chunks = []
        self._recording = True
        try:
            device = self._resolve_input_device()
            self._stream = sd.InputStream(
                samplerate=self._sample_rate, channels=1, dtype="float32",
                callback=self._audio_callback, device=device,
            )
            self._stream.start()
        except Exception as exc:
            print(f"[触发] 录音设备打开失败: {exc}")
            print("       检查：系统默认输入设备（设置→声音→输入）和麦克风权限")
            self._recording = False
            self._stream = None

    def _resolve_input_device(self) -> int | None:
        """按关键字匹配输入设备；空关键字返回 None（默认输入）。"""
        if not self._input_device:
            return None
        devices = [d for d in sd.query_devices()
                   if d.get("max_input_channels", 0) > 0]
        dev = match_device_by_keyword(devices, self._input_device)
        if dev is not None:
            print(f"[触发] 使用麦克风: {dev['name']}")
            return int(dev["index"])
        print(f"[触发] 未找到匹配 '{self._input_device}' 的输入设备，使用默认")
        return None

    def _stop_and_process(self):
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        audio = np.concatenate(self._chunks) if self._chunks else np.array([], dtype="float32")
        duration = len(audio) / self._sample_rate
        if duration < 0.3:
            print("[触发] 录音太短，忽略")
            return
        print(f"[触发] 录音结束（{duration:.1f}s），识别中...")
        # 识别放后台线程：ctranslate2 推理在录音主线程会触发 cffi 崩溃，
        # 且异步化后松开 F8 立即恢复监听，不影响连续说话
        threading.Thread(target=self._process_audio, args=(audio,), daemon=True).start()

    def _process_audio(self, audio: np.ndarray) -> None:
        # 清洗：麦克风偶发 NaN/inf 会让 ctranslate2 的 C 层直接段错误
        if not np.all(np.isfinite(audio)):
            print(f"[触发] 音频含异常样本，清洗 {int(np.sum(~np.isfinite(audio)))} 个")
            audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
        # 崩溃现场留存：识别前保存音频，便于分析（用完可删）
        np.save("last_recording.npy", audio)
        text = self._recognizer.transcribe(audio)
        if text:
            print(f"[触发] 你说: {text}")
            self._bus.publish(SpeechCaptured(text=text))
        else:
            print("[触发] 没听清，再试一次？")

    # ---------- 主循环 ----------
    def run(self) -> None:
        import keyboard

        # 用 is_pressed 轮询而非 add_hotkey 钩子回调：
        # keyboard 钩子线程里操作 PortAudio 流会污染线程状态，
        # 导致后续 ctranslate2 推理段错误（SIGSEGV/SIGILL）
        try:
            dev = sd.query_devices(kind="input")
            print(f"[触发] 默认输入设备: {dev['name']}")
        except Exception:
            pass
        print(f"[触发] 就绪：按住 [{self._hotkey}] 说话，松开识别。Ctrl+C 退出。")
        try:
            while True:
                pressed = keyboard.is_pressed(self._hotkey)
                if pressed and not self._recording:
                    self._start()
                elif self._recording and not pressed:
                    self._stop_and_process()
                time.sleep(0.02)
        except KeyboardInterrupt:
            print("\n[触发] 退出。")
