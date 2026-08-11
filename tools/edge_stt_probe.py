"""EdgeSTT 最小验证：连接微软 Edge 免费语音端点，识别一段 PCM16 音频。

用法: python tools/edge_stt_probe.py <wav_pcm16_48k单声道>
协议参考 kikitan-translator src/recognizers/EdgeSTT.ts
"""
from __future__ import annotations

import asyncio
import hashlib
import struct
import sys
import time
import uuid

import numpy as np
import websockets

TRUSTED_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
MS_VERSION = "1-145.0.3800.70"
EPOCH = 11644473600


def sec_ms_gec() -> str:
    now = int(time.time())
    ticks = (now + EPOCH) * 10_000_000
    rounded = ticks - (ticks % 300_000_000)
    data = f"{rounded}{TRUSTED_TOKEN}".encode()
    return hashlib.sha256(data).hexdigest().upper()


def ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def text_msg(path: str, body: dict, request_id: str | None = None) -> str:
    headers = [f"X-Timestamp:{ts()}", f"Path:{path}"]
    if request_id:
        headers.append(f"X-RequestId:{request_id}")
    return "\r\n".join(headers) + "\r\n\r\n" + __import__("json").dumps(body)


def bin_msg(path: str, stream_id: str, request_id: str, payload: bytes, ctype: str) -> bytes:
    headers = [f"X-Timestamp:{ts()}", f"Path:{path}", f"X-RequestId:{request_id}"]
    if ctype:
        headers.append(f"Content-Type:{ctype}")
    if stream_id:
        headers.append(f"X-StreamId:{stream_id}")
    h = "\r\n".join(headers).encode()
    return struct.pack(">H", len(h)) + h + payload


def wav_header(sample_rate: int) -> bytes:
    data = b"RIFF" + struct.pack("<I", 0) + b"WAVE" + b"fmt "
    data += struct.pack("<IHHIIHH", 16, 1, 1, sample_rate,
                        sample_rate * 2, 2, 16)
    data += b"data" + struct.pack("<I", 0)
    return data


def parse_server_msg(raw: bytes | str) -> dict:
    if isinstance(raw, bytes):
        if len(raw) < 2:
            return {"path": "", "body": ""}
        hlen = struct.unpack(">H", raw[:2])[0]
        text = raw[2:2 + hlen].decode("utf-8", "ignore")
        body = raw[2 + hlen:].decode("utf-8", "ignore")
    else:
        parts = raw.split("\r\n\r\n", 1)
        text, body = parts[0], parts[1] if len(parts) > 1 else ""
    path = ""
    for line in text.split("\r\n"):
        if line.startswith("Path:"):
            path = line[5:]
    return {"path": path, "body": body}


async def recognize(pcm_path: str, language: str = "zh-CN") -> list[str]:
    gec = sec_ms_gec()
    url = (f"wss://speech.platform.bing.com/speech/recognition/edge/interactive/v1"
           f"?TrustedClientToken={TRUSTED_TOKEN}&Sec-MS-GEC={gec}"
           f"&Sec-MS-GEC-Version={MS_VERSION}&language={language}&profanity=raw")
    print(f"[probe] 连接: {url[:120]}...")

    results: list[str] = []
    async with websockets.connect(url, max_size=10 * 1024 * 1024,
                                  open_timeout=30) as ws:
        req_id = uuid.uuid4().hex
        await ws.send(text_msg("speech.config", {
            "context": {
                "audio": {"source": {"bitspersample": "16", "channelcount": "1",
                                     "model": "", "samplerate": "48000",
                                     "type": "Stream"}},
                "os": {"name": "Client", "platform": "Windows", "version": "10"},
                "system": {"build": "Windows-x64", "name": "SpeechSDK",
                           "version": "1.15.0"},
            },
        }))
        await ws.send(text_msg("speech.context",
                               {"audio": {"streams": {"1": None}}}, req_id))

        pcm = np.fromfile(pcm_path, dtype=np.int16)
        print(f"[probe] 音频: {len(pcm)} 样本 ({len(pcm)/48000:.1f}s)")

        # WAV 头（stream 1）
        await ws.send(bin_msg("audio", "1", req_id, wav_header(48000),
                              "audio/x-wav"))
        # 分块发 PCM
        chunk_size = 4800 * 2  # 100ms
        for i in range(0, len(pcm), chunk_size):
            chunk = pcm[i:i + chunk_size].tobytes()
            await ws.send(bin_msg("audio", "1", req_id, chunk, "audio/x-wav"))
            await asyncio.sleep(0.05)
        # 结束标记
        await ws.send(bin_msg("audio", "1", req_id, b"", "audio/x-wav"))

        # 收结果
        end_time = time.time() + 30
        while time.time() < end_time:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
            except asyncio.TimeoutError:
                break
            msg = parse_server_msg(raw)
            if "turn.start" in msg["path"]:
                print("[probe] ✓ turn.start（握手成功，服务已接收音频）")
            elif "speech.hypothesis" in msg["path"]:
                print(f"[probe] 中间结果: {msg['body'][:80]}")
            elif "speech.phrase" in msg["path"]:
                import json
                try:
                    data = json.loads(msg["body"])
                    text = data.get("DisplayText", "")
                    if text:
                        results.append(text)
                        print(f"[probe] ★ 最终识别: {text}")
                except Exception:
                    pass
            elif "turn.end" in msg["path"]:
                print("[probe] turn.end")
                break
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tools/edge_stt_probe.py <pcm16_48k_mono>")
        sys.exit(1)
    out = asyncio.run(recognize(sys.argv[1]))
    print(f"\n[probe] 识别结果: {out}")
