"""EdgeRecognizer：微软 Edge 免费语音服务（对标 kikitan-translator 的 EdgeSTT）。

原理：逆向 Edge 浏览器内置语音识别的云端端点（Azure Speech 同源）：
- WSS 连接 speech.platform.bing.com，TrustedClientToken + Sec-MS-GEC 签名
- 声明音频格式（16bit PCM / 单声道 / 48kHz）→ 流式推送 PCM → 收 speech.phrase
- 免费、无 Key、中文识别精度远超本地 whisper small，服务端自带 VAD 抗音乐

**长连接复用**（对齐 kikitan）：一次 WSS 连接持续多轮识别（turn.end 后发新
speech.context 续传），避免每段新建连接——既降低延迟，也规避高频连接限流。
连接空闲被服务器关闭时自动重建；transcribe 加锁保证多线程（F8+auto）安全。

输入为 16kHz 单声道 float32（与 WhisperRecognizer 一致），内部重采样到 48kHz。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import struct
import threading
import time
import uuid

import numpy as np
import websockets
from websockets.protocol import State

from vrchat_ai.infrastructure.audio_utils import resample
from vrchat_ai.interfaces.speech import SpeechRecognizer

TRUSTED_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
MS_VERSION = "1-145.0.3800.70"
_EPOCH = 11644473600  # 1601-01-01 → 1970-01-01 的 100ns tick 差
_TARGET_RATE = 48000
_CHUNK_SAMPLES = 4800  # 100ms


def sec_ms_gec() -> str:
    """生成 Sec-MS-GEC 签名：SHA256(取整到300s的ticks + TRUSTED_TOKEN) 大写 hex。"""
    ticks = (int(time.time()) + _EPOCH) * 10_000_000
    rounded = ticks - (ticks % 300_000_000)
    return hashlib.sha256(f"{rounded}{TRUSTED_TOKEN}".encode()).hexdigest().upper()


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _text_msg(path: str, body: dict, request_id: str | None = None) -> str:
    headers = [f"X-Timestamp:{_ts()}", f"Path:{path}"]
    if request_id:
        headers.append(f"X-RequestId:{request_id}")
    return "\r\n".join(headers) + "\r\n\r\n" + json.dumps(body)


def _bin_msg(path: str, stream_id: str, request_id: str, payload: bytes, ctype: str) -> bytes:
    headers = [f"X-Timestamp:{_ts()}", f"Path:{path}", f"X-RequestId:{request_id}",
               f"Content-Type:{ctype}"]
    if stream_id:
        headers.append(f"X-StreamId:{stream_id}")
    h = "\r\n".join(headers).encode()
    return struct.pack(">H", len(h)) + h + payload


def _wav_header(sample_rate: int) -> bytes:
    data = b"RIFF" + struct.pack("<I", 0) + b"WAVE" + b"fmt "
    data += struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data += b"data" + struct.pack("<I", 0)
    return data


def parse_server_msg(raw: bytes | str) -> tuple[str, str]:
    """解析服务器消息：返回 (Path, body)。"""
    if isinstance(raw, bytes):
        if len(raw) < 2:
            return "", ""
        hlen = struct.unpack(">H", raw[:2])[0]
        text = raw[2:2 + hlen].decode("utf-8", "ignore")
        body = raw[2 + hlen:].decode("utf-8", "ignore")
    else:
        parts = raw.split("\r\n\r\n", 1)
        text, body = parts[0], parts[1] if len(parts) > 1 else ""
    path = next((ln[5:] for ln in text.split("\r\n") if ln.startswith("Path:")), "")
    return path, body


def to_edge_language(lang: str) -> str:
    """whisper 语言码 → Edge 区域码（未知直接透传）。"""
    return {"zh": "zh-CN", "en": "en-US", "ja": "ja-JP", "ko": "ko-KR",
            "ru": "ru-RU", "fr": "fr-FR", "de": "de-DE"}.get(lang, lang)


class EdgeRecognizer(SpeechRecognizer):
    """策略实现：微软 Edge 云语音识别（长连接复用）。

    输入 16kHz 单声道 float32。后台线程常驻 event loop，
    transcribe 通过 run_coroutine_threadsafe 提交，连接跨调用复用。
    """

    def __init__(self, language: str = "zh-CN", sample_rate: int = 16000,
                 timeout: float = 30.0, idle_keepalive_s: float = 600.0,
                 max_retries: int = 1) -> None:
        self._lang = language
        self._sr = sample_rate
        self._timeout = timeout
        # 连接生命周期对齐 kikitan（应用级）：空闲不主动关，只有坏了才重建。
        # 拉长到 10 分钟，避免"每句一连接"导致限流。
        self._idle_limit = idle_keepalive_s
        self._max_retries = max_retries
        self._lock = threading.Lock()
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._stream_counter = 0
        self._last_used = 0.0
        # 常驻 event loop（长连接必须跨 transcribe 调用复用同一 loop）
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever,
                                             daemon=True, name="edge-stt-loop")
        self._loop_thread.start()

    # ---------- 策略接口 ----------
    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) < self._sr * 0.3:  # 少于 0.3 秒视为无效
            return ""
        with self._lock:  # 多线程（F8+auto）串行使用连接
            for attempt in range(self._max_retries + 1):
                future = asyncio.run_coroutine_threadsafe(
                    self._recognize_async(audio), self._loop)
                try:
                    return future.result(timeout=self._timeout + 15)
                except Exception as exc:
                    if attempt < self._max_retries:
                        # 连接可能被服务器静默关闭：丢弃重建后重试一次
                        print(f"[EDGE-STT] 连接异常({exc})，重建重试...")
                        asyncio.run_coroutine_threadsafe(self._close_async(), self._loop)
                        continue
                    print(f"[EDGE-STT] 识别失败: {exc}")
                    asyncio.run_coroutine_threadsafe(self._close_async(), self._loop)
                    return ""

    # ---------- 协议实现 ----------
    async def _recognize_async(self, audio: np.ndarray) -> str:
        audio48 = resample(audio, self._sr, _TARGET_RATE)
        pcm16 = (np.clip(audio48, -1.0, 1.0) * 32767).astype(np.int16)

        ws = await self._get_ws()
        self._stream_counter += 1
        req_id = uuid.uuid4().hex
        stream_id = str(self._stream_counter)

        # 新一轮：声明流 → WAV 头 → PCM 流 → 结束标记
        await ws.send(_text_msg("speech.context",
                                {"audio": {"streams": {"1": None}}}, req_id))
        await ws.send(_bin_msg("audio", stream_id, req_id,
                               _wav_header(_TARGET_RATE), "audio/x-wav"))
        for i in range(0, len(pcm16), _CHUNK_SAMPLES):
            chunk = pcm16[i:i + _CHUNK_SAMPLES].tobytes()
            await ws.send(_bin_msg("audio", stream_id, req_id, chunk, "audio/x-wav"))
            await asyncio.sleep(0.03)
        await ws.send(_bin_msg("audio", stream_id, req_id, b"", "audio/x-wav"))

        # 收最终结果
        deadline = time.time() + self._timeout
        display_texts: list[str] = []
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
            except asyncio.TimeoutError:
                break
            path, body = parse_server_msg(raw)
            if "speech.phrase" in path and body:
                try:
                    data = json.loads(body)
                    if data.get("DisplayText"):
                        display_texts.append(data["DisplayText"])
                except json.JSONDecodeError:
                    pass
            elif "turn.end" in path:
                break
        self._last_used = time.time()
        return display_texts[0] if display_texts else ""

    async def _get_ws(self) -> websockets.WebSocketClientProtocol:
        # 连接 OPEN 就直接复用（空闲不主动关，对齐 kikitan 应用级生命周期）
        if self._ws is not None and self._ws.state is State.OPEN:
            return self._ws
        await self._close_async()
        gec = sec_ms_gec()
        url = (f"wss://speech.platform.bing.com/speech/recognition/edge/interactive/v1"
               f"?TrustedClientToken={TRUSTED_TOKEN}&Sec-MS-GEC={gec}"
               f"&Sec-MS-GEC-Version={MS_VERSION}&language={self._lang}&profanity=raw")
        self._ws = await websockets.connect(url, max_size=10 * 1024 * 1024,
                                            open_timeout=15)
        # 连接建立只发一次音频格式声明，后续轮次只发 speech.context
        await self._ws.send(_text_msg("speech.config", {
            "context": {
                "audio": {"source": {"bitspersample": "16", "channelcount": "1",
                                     "model": "", "samplerate": str(_TARGET_RATE),
                                     "type": "Stream"}},
                "os": {"name": "Client", "platform": "Windows", "version": "10"},
                "system": {"build": "Windows-x64", "name": "SpeechSDK",
                           "version": "1.15.0"},
            },
        }))
        self._stream_counter = 0
        self._last_used = time.time()
        return self._ws

    async def _close_async(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
