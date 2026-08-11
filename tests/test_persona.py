"""人设系统：角色卡加载与 system prompt 渲染。"""
import pytest

from config import PERSONAS_DIR
from vrchat_ai.application.persona_manager import PersonaManager


@pytest.fixture
def manager():
    return PersonaManager(PERSONAS_DIR)


def test_load_persona_card(manager):
    persona = manager.load("xiaoxing")
    assert persona.name == "小星"
    assert persona.emoji == "✨"
    assert persona.personality


def test_render_system_prompt_contains_persona(manager):
    prompt = manager.load("xiaoxing").render_system_prompt()
    assert "小星" in prompt
    assert "100" in prompt  # 字数限制
    assert "硬性要求" in prompt


def test_load_missing_persona_raises(manager):
    with pytest.raises(FileNotFoundError):
        manager.load("不存在的角色")


def test_load_default_picks_first(manager):
    assert manager.load_default().name == "小星"
