"""OSC 聊天框：协议格式（UDP 真实收发验证）。"""
import socket

import pytest
from pythonosc import osc_message

from vrchat_ai.infrastructure.osc_chatbox import OscChatbox


@pytest.fixture
def udp_listener(udp_port):
    """在临时端口起一个 UDP 监听，模拟 VRChat OSC 端点。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", udp_port))
    sock.settimeout(3)
    yield sock
    sock.close()


def _collect(sock, n):
    """收 n 条消息并解析为 (address, params)。"""
    msgs = []
    for _ in range(n):
        try:
            msg = osc_message.OscMessage(sock.recv(65535))
            msgs.append((msg.address, msg.params))
        except socket.timeout:
            break
    return msgs


def test_typing_message_format(udp_listener, udp_port):
    box = OscChatbox("127.0.0.1", udp_port)
    box.typing(True)
    msgs = _collect(udp_listener, 1)
    assert any(a == "/chatbox/typing" and p == [True] for a, p in msgs)


def test_input_message_format(udp_listener, udp_port):
    box = OscChatbox("127.0.0.1", udp_port)
    box.send("协议测试")
    msgs = _collect(udp_listener, 1)
    # VRChat 规范: [文本, 清空, 通知气泡]
    assert any(a == "/chatbox/input" and p == ["协议测试", True, True] for a, p in msgs)


def test_long_text_split_into_multiple(udp_listener, udp_port):
    box = OscChatbox("127.0.0.1", udp_port, max_len=20)
    box.send("超长文本" * 10)  # 40 字 → 2 段
    msgs = _collect(udp_listener, 5)
    inputs = [p[0] for a, p in msgs if a == "/chatbox/input"]
    assert len(inputs) == 2
    assert all(len(t) <= 20 for t in inputs)
