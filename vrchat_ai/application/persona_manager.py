"""人设管理器：从角色卡 JSON 加载 Persona。

换角色 = 往 personas/ 目录丢一个 JSON 文件，无需改任何代码（开闭原则）。
"""
from __future__ import annotations

import json
from pathlib import Path

from vrchat_ai.domain.models import Persona


class PersonaManager:
    def __init__(self, personas_dir: Path) -> None:
        self._dir = personas_dir

    def list_personas(self) -> list[str]:
        return sorted(p.stem for p in self._dir.glob("*.json"))

    def load(self, name: str) -> Persona:
        path = self._dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"角色卡不存在: {path}（可用: {self.list_personas()}）")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Persona(**data)

    def load_default(self) -> Persona:
        """加载第一个可用角色卡（按文件名排序）。"""
        names = self.list_personas()
        if not names:
            raise FileNotFoundError(f"personas 目录为空: {self._dir}")
        return self.load(names[0])
