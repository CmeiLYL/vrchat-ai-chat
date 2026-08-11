"""文本后处理管道：责任链模式。"""
from vrchat_ai.application.text_pipeline import build_default_pipeline


def test_long_text_split_within_limit():
    pipe = build_default_pipeline(max_len=50)
    chunks = pipe.process_chain("很长" * 40)
    assert len(chunks) >= 2
    assert all(len(c) <= 50 for c in chunks)


def test_emoji_normalized():
    pipe = build_default_pipeline()
    chunks = pipe.process_chain("你好呀 :) 今天开心")
    assert "😊" in chunks[0]
    assert ":)" not in chunks[0]


def test_whitespace_cleaned():
    pipe = build_default_pipeline()
    chunks = pipe.process_chain("  你好   世界  ")
    assert chunks[0] == "你好 世界"


def test_short_text_passthrough():
    pipe = build_default_pipeline()
    assert pipe.process_chain("短消息") == ["短消息"]
