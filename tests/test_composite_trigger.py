"""CompositeTrigger：组合模式（多触发通道同时运行）。"""
import threading
import time

import pytest

from vrchat_ai.infrastructure.composite_trigger import CompositeTrigger
from vrchat_ai.interfaces.trigger import AudioTrigger


class _FakeTrigger(AudioTrigger):
    def __init__(self, name: str, delay: float = 0.3):
        self.name = name
        self.delay = delay
        self.started = False
        self._event = threading.Event()

    def run(self) -> None:
        self.started = True
        self._event.set()
        time.sleep(self.delay)


def test_composite_runs_all_triggers():
    t1, t2 = _FakeTrigger("监听", 0.3), _FakeTrigger("热键", 0.5)
    comp = CompositeTrigger([t1, t2])
    t0 = time.time()
    comp.run()
    elapsed = time.time() - t0
    assert t1.started and t2.started          # 两个通道都启动了
    assert elapsed < 2.0                       # 子线程结束后主循环返回


def test_composite_requires_nonempty():
    with pytest.raises(ValueError):
        CompositeTrigger([])


def test_composite_implements_interface():
    assert issubclass(CompositeTrigger, AudioTrigger)
