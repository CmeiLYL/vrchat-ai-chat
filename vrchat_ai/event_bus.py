"""事件总线：观察者模式的实现。

发布者不知道订阅者是谁，订阅者也不知道发布者是谁，
靠事件类型解耦 —— 输入输出两侧互不感知。
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable

from vrchat_ai.domain.events import Event

Handler = Callable[[Event], None]


class EventBus:
    """线程安全的同步事件总线。"""

    def __init__(self) -> None:
        self._subscribers: dict[type, list[Handler]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: type[Event], handler: Handler) -> None:
        with self._lock:
            self._subscribers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        """发布事件：调用该类型所有订阅者（含子类匹配）。"""
        with self._lock:
            handlers = list(self._subscribers.get(type(event), []))
        for handler in handlers:
            handler(event)
