"""文本处理抽象：责任链模式的抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class TextProcessor(ABC):
    """文本后处理环节（清洗 / 分段 / 过滤...）。

    责任链模式：每个环节处理完决定是否交给下一个。
    """

    def __init__(self) -> None:
        self._next: TextProcessor | None = None

    def set_next(self, next_processor: "TextProcessor") -> "TextProcessor":
        """设置链上下一环，返回下一环便于链式构建。"""
        self._next = next_processor
        return next_processor

    def process_chain(self, text: str) -> list[str]:
        """沿着链处理，最终产出若干条可发送的文本。"""
        result = self._handle(text)
        if self._next is None:
            return result
        # 本环节产出多条时，每条都继续走后续环节
        if isinstance(result, list):
            output: list[str] = []
            for item in result:
                output.extend(self._next.process_chain(item))
            return output
        return self._next.process_chain(result)

    @abstractmethod
    def _handle(self, text: str) -> str | list[str]:
        """本环节的处理逻辑。"""
        raise NotImplementedError
