"""探测脚本：验证本机 WASAPI loopback 能否捕获到 VRChat 输出。

用法（在 VRChat 里让其他人说话 / 播放音乐，观察能量条）：
    .venv/Scripts/python.exe tools/probe_audio.py
    .venv/Scripts/python.exe tools/probe_audio.py CABLE   # 指定捕获 VB-Cable

原理：pyaudiowpatch 的 loopback 捕获"正在播放的声音"（即 VRChat 语音
输出去向）。本脚本只测"能不能听到"，跑通后再开 main.py 的 auto 模式。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from vrchat_ai.infrastructure.audio_utils import resample, to_mono
from vrchat_ai.infrastructure.auto_trigger import open_loopback_stream, select_loopback_device

DURATION_S = 10


def main() -> None:
    keyword = sys.argv[1] if len(sys.argv) > 1 else ""
    print("=" * 56)
    print("WASAPI loopback 探测：捕获系统正在播放的声音")
    print("请在 VRChat 里说话/放音乐，观察能量值是否跳动")
    print("=" * 56)

    import pyaudiowpatch as pyaudio

    pa = pyaudio.PyAudio()
    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_name = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])["name"]
        print(f"默认输出设备: {default_name}")

        candidates = list(pa.get_loopback_device_info_generator())
        print(f"可用 loopback 设备: {len(candidates)} 个")
        for dev in candidates:
            print(f"  · {dev['name']}")

        loopback = select_loopback_device(candidates, default_name, keyword)
        if loopback is None:
            print("\n❌ 找不到目标 loopback 设备")
            if keyword:
                print("   可指定关键字，如: probe_audio.py CABLE")
            sys.exit(1)
        print(f"\n将捕获: {loopback['name']}")
    except Exception as exc:
        print(f"\n❌ loopback 枚举失败: {exc}")
        pa.terminate()
        sys.exit(1)

    src_rate = int(loopback["defaultSampleRate"])
    channels = max(1, int(loopback.get("maxInputChannels", 2)) or 2)
    print(f"监听 {DURATION_S} 秒...（Ctrl+C 提前结束）")

    levels: list[float] = []

    def callback(in_data, frame_count, time_info, status):
        try:
            audio = np.frombuffer(in_data, dtype=np.float32)
            if channels > 1:
                audio = audio.reshape(-1, channels)
            chunk = resample(to_mono(audio), src_rate, 16000)
            levels.append(float(np.sqrt(np.mean(chunk**2))))
        except Exception as exc:
            print(f"  [回调异常] {exc}")
        return None, pyaudio.paContinue

    stream, channels, src_rate = open_loopback_stream(pa, loopback, callback)
    try:
        stream.start_stream()
        end = time.time() + DURATION_S
        while time.time() < end:
            time.sleep(0.5)
            if levels:
                db = 20 * np.log10(max(levels[-1], 1e-9))
                bar = "█" * max(0, int((db + 60) / 2))
                print(f"  RMS {db:6.1f} dB  {bar}")
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

    print("-" * 56)
    if levels and 20 * np.log10(max(float(np.mean(levels)), 1e-9)) > -50:
        print("✅ 捕获正常：说话时能量应明显跳动，现在可设 TRIGGER_MODE=auto 运行 main.py")
    else:
        print("⚠️  几乎没听到声音（能量过低）。检查：")
        print("   1. 目标设备是不是 VRChat 语音的输出去向（可试 probe_audio.py CABLE）")
        print("   2. 游戏里是否真的有人说话/有音乐")
        print("   3. Windows 音量合成器里 VRChat 是否静音")


if __name__ == "__main__":
    main()
