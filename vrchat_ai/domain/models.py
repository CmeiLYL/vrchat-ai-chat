"""领域模型：纯数据类，不依赖任何外部库。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    """对话消息（不可变，防误改历史）。"""
    role: Role
    content: str

    def to_api_dict(self) -> dict:
        return {"role": self.role.value, "content": self.content}


@dataclass(frozen=True)
class Persona:
    """AI 人设：从角色卡 JSON 加载，渲染成 system prompt。

    换角色 = 新增一个 JSON 文件，无需改代码（开闭原则）。
    """
    name: str
    emoji: str = ""
    personality: str = ""
    background: str = ""
    speaking_style: str = ""
    constraints: dict = field(default_factory=dict)
    examples: list[dict] = field(default_factory=list)

    def render_system_prompt(self) -> str:
        """把人设各字段渲染成给 LLM 的系统提示词。"""
        lines = [
            f"你现在的角色是「{self.name}」{self.emoji}。",
        ]
        if self.personality:
            lines.append(f"性格：{self.personality}")
        if self.background:
            lines.append(f"背景：{self.background}")
        if self.speaking_style:
            lines.append(f"说话风格：{self.speaking_style}")

        max_chars = self.constraints.get("max_chars", 100)
        lines.append(f"硬性要求：回复控制在 {max_chars} 个中文字符以内（通过游戏聊天框显示）。")
        if self.constraints.get("no_markdown", True):
            lines.append("不要使用 markdown 格式标记。")

        topics = self.constraints.get("topic_focus")
        if topics:
            lines.append(f"擅长话题：{'、'.join(topics)}")

        if self.examples:
            lines.append("对话示例（仅参考语气，不要照抄）：")
            for ex in self.examples[:3]:
                lines.append(f"  用户：{ex.get('user', '')}")
                lines.append(f"  你：{ex.get('assistant', '')}")

        return "\n".join(lines)


@dataclass
class Conversation:
    """对话会话：持有系统提示 + 历史消息，负责截断。"""
    system_prompt: str
    history: list[ChatMessage] = field(default_factory=list)
    max_rounds: int = 8

    def add(self, role: Role, content: str) -> None:
        self.history.append(ChatMessage(role, content))
        self._trim()

    def _trim(self) -> None:
        """只保留最近 max_rounds 轮，防止上下文无限膨胀。"""
        keep = self.max_rounds * 2  # 每轮 = 一问一答两条
        if len(self.history) > keep:
            self.history = self.history[-keep:]

    def to_api_messages(self) -> list[ChatMessage]:
        return [ChatMessage(Role.SYSTEM, self.system_prompt)] + self.history
