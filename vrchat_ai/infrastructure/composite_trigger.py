"""CompositeTrigger：组合模式——多个触发策略同时运行。

用法：auto 监听（公共）+ F8 手动（私人）同时生效，
两者都发布 SpeechCaptured 事件到同一事件总线，业务层无感知。
"""
from __future__ import annotations

import threading
import time

from vrchat_ai.interfaces.trigger import AudioTrigger


class CompositeTrigger(AudioTrigger):
    """组合模式：内部持有多个触发器，run() 时各自独立线程运行。"""

    def __init__(self, triggers: list[AudioTrigger]) -> None:
        if not triggers:
            raise ValueError("CompositeTrigger 至少需要一个子触发器")
        self._triggers = triggers

    def run(self) -> None:
        threads = [threading.Thread(target=t.run, daemon=True) for t in self._triggers]
        for t in threads:
            t.start()
        print(f"[触发] 已启动 {len(threads)} 个触发通道（Ctrl+C 退出）")
        try:
            # 主循环等子线程；全部退出（如测试 mock）时自然返回
            while any(t.is_alive() for t in threads):
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n[触发] 退出。")
