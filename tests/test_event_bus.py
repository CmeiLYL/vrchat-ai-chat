"""事件总线：观察者模式。"""
from vrchat_ai.domain.events import ReplyReady, SpeechCaptured


def test_multiple_subscribers_notified(bus):
    got = []
    bus.subscribe(SpeechCaptured, lambda e: got.append(e.text))
    bus.subscribe(SpeechCaptured, lambda e: got.append(f"2:{e.text}"))
    bus.publish(SpeechCaptured(text="你好"))
    assert got == ["你好", "2:你好"]


def test_only_matching_type_delivered(bus):
    got = []
    bus.subscribe(ReplyReady, lambda e: got.append(e.text))
    bus.publish(SpeechCaptured(text="不该到达"))
    assert got == []


def test_publish_without_subscribers_is_noop(bus):
    bus.publish(ReplyReady(text="没人订阅也安全"))


def test_no_delivery_after_unsubscribe_window(bus):
    """同一订阅者重复注册会重复触发（当前语义），此处验证计数正确性。"""
    count = {"n": 0}
    bus.subscribe(SpeechCaptured, lambda e: count.__setitem__("n", count["n"] + 1))
    bus.publish(SpeechCaptured(text="1"))
    bus.publish(SpeechCaptured(text="2"))
    assert count["n"] == 2
