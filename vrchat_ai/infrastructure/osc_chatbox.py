"""OSC 聊天框实现：把文字写进 VRChat 聊天框。

VRChat OSC 速览：
- 程序向 127.0.0.1:9000 发送（VRChat 监听端口）
- /chatbox/input  参数: [文本(str), 是否清空(bool), 是否通知(bool)]
- /chatbox/typing 参数: [是否正在输入(bool)]
"""
from __future__ import annotations

import time

from pythonosc.udp_client import SimpleUDPClient

from vrchat_ai.interfaces.chatbox import ChatboxSender


class OscChatbox(ChatboxSender):
    """策略模式的具体策略：VRChat OSC 通道。"""

    def __init__(self, host: str, port: int, max_len: int = 144) -> None:
        self._client = SimpleUDPClient(host, port)
        self._max_len = max_len
        self._notify = True  # 弹聊天气泡

    def typing(self, on: bool) -> None:
        try:
            self._client.send_message("/chatbox/typing", [bool(on)])
        except Exception as exc:
            print(f"[OSC] typing 失败（VRChat OSC 是否已开启？）: {exc}")

    def send(self, text: str) -> None:
        # VRChat 单条聊天框最多 144 字符，超长自动分段
        for chunk in self._split(text):
            try:
                # [文本, 清空旧内容, 通知气泡]
                self._client.send_message("/chatbox/input", [chunk, True, self._notify])
                time.sleep(0.2)  # 分段间留间隔，避免被吞
            except Exception as exc:
                print(f"[OSC] 发送失败: {exc}")

    def _split(self, text: str) -> list[str]:
        if len(text) <= self._max_len:
            return [text]
        chunks, current = [], ""
        for ch in text:
            if len(current) >= self._max_len:
                chunks.append(current)
                current = ch
            else:
                current += ch
        if current:
            chunks.append(current)
        return chunks
