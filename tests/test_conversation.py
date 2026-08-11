"""会话历史：截断与角色顺序。"""
from vrchat_ai.domain.models import Conversation, Role


def _fill(conv, rounds):
    for i in range(rounds):
        conv.add(Role.USER, f"q{i}")
        conv.add(Role.ASSISTANT, f"a{i}")


def test_history_trimmed_to_max_rounds():
    conv = Conversation(system_prompt="sys", max_rounds=2)
    _fill(conv, 20)
    assert len(conv.to_api_messages()) == 1 + 2 * 2


def test_first_message_is_system():
    conv = Conversation(system_prompt="sys", max_rounds=8)
    _fill(conv, 3)
    assert conv.to_api_messages()[0].role == Role.SYSTEM


def test_keeps_latest_messages():
    conv = Conversation(system_prompt="sys", max_rounds=2)
    _fill(conv, 20)
    messages = conv.to_api_messages()
    assert messages[-1].content == "a19"
    assert messages[1].content == "q18"  # 丢掉最老的，保留最新的


def test_message_roles_serialized_correctly():
    conv = Conversation(system_prompt="sys")
    conv.add(Role.USER, "hi")
    api = conv.to_api_messages()
    assert api[1].to_api_dict() == {"role": "user", "content": "hi"}
