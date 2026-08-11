"""文本后处理管道：责任链模式的实现。

链：清洗(去空行/首尾空白) → 表情规范化 → 分段(144 字上限)
每个环节实现 TextProcessor，链式组合，可自由增删环节。
"""
from __future__ import annotations

import re

from vrchat_ai.interfaces.text import TextProcessor


class Cleaner(TextProcessor):
    """环节1：清理空白与多余换行。"""

    def _handle(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text


class EmojiNormalizer(TextProcessor):
    """环节2：把 (^_^) 等文本表情替换为 emoji，提升聊天框观感。"""

    _MAP = {
        "(^_^)": "😊", ":-)": "😊", ":)": "😊",
        ":-(": "😢", ":(": "😢",
        "XD": "😆", "xd": "😆",
    }

    def _handle(self, text: str) -> str:
        for k, v in self._MAP.items():
            text = text.replace(k, v)
        return text


class Splitter(TextProcessor):
    """环节3：按 VRChat 聊天框字数上限分段（终点环节）。"""

    def __init__(self, max_len: int = 144) -> None:
        super().__init__()
        self._max_len = max_len

    def _handle(self, text: str) -> list[str]:
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


def build_default_pipeline(max_len: int = 144) -> TextProcessor:
    """构建默认处理链（工厂方法：返回链头）。"""
    head = Cleaner()
    head.set_next(EmojiNormalizer()).set_next(Splitter(max_len))
    return head
