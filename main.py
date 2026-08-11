"""VRChat AI 聊天 —— 入口（组装根 / Composition Root）。

依赖注入集中点：在这里把各个策略装配起来，
main 不关心任何实现细节，只负责"组装 + 启动"。

用法：
    python main.py                正常启动（按住 F8 说话）
    python main.py --selftest     自测全链路（Mock LLM + 控制台通道，不联网）
"""
from __future__ import annotations

import argparse
import sys

from config import PERSONAS_DIR, load_config
from vrchat_ai.application.chat_service import ChatService
from vrchat_ai.application.persona_manager import PersonaManager
from vrchat_ai.application.text_pipeline import build_default_pipeline
from vrchat_ai.domain.events import ReplyReady
from vrchat_ai.event_bus import EventBus
from vrchat_ai.factories import ProviderFactory


class Application:
    """组装根：把全部依赖装配好，对外暴露运行入口。"""

    def __init__(self, config) -> None:
        self.config = config
        bus = EventBus()
        factory = ProviderFactory(config)
        personas = PersonaManager(PERSONAS_DIR)
        persona = personas.load(config.persona) if config.persona else personas.load_default()

        self.service = ChatService(
            persona=persona,
            llm=factory.create_llm(),
            chatbox=factory.create_chatbox(),
            pipeline=build_default_pipeline(max_len=config.chatbox_max_len),
            bus=bus,
            max_rounds=config.max_rounds,
        )
        # 观察者演示：ReplyReady 的第二个订阅者（控制台侧边记录）
        bus.subscribe(ReplyReady, lambda e: print(f"  ↳ [事件] ReplyReady: {e.text[:24]}..."))

        # 音频触发策略（f8 私人 / auto 公共），由工厂装配
        self._trigger = factory.create_trigger(bus=bus)

    @property
    def persona(self):
        return self.service.persona

    def run(self) -> None:
        self._trigger.run()


def selftest(config) -> None:
    """不联网、不需要 VRChat 的整链路自测（Mock LLM + 控制台通道 + Mock 识别）。"""
    print("=" * 56)
    print("自测：MockProvider + ConsoleChatbox（全离线）")
    test_cfg = config.__class__(
        **{**config.__dict__, "llm_provider": "mock", "chatbox_channel": "console",
           "whisper_model": "mock"})
    app = Application(test_cfg)
    print(f"人设: {app.persona.name} {app.persona.emoji}")
    print("-" * 56)
    app.service.handle_user_text("你好")
    app.service.handle_user_text("测试一下责任链管道")
    print("-" * 56)
    print("✅ 链路自测通过（输入 → 人设 → LLM → 责任链 → 输出）")


def main() -> None:
    parser = argparse.ArgumentParser(description="VRChat AI 聊天")
    parser.add_argument("--selftest", action="store_true", help="全链路离线自测")
    args = parser.parse_args()

    config = load_config()

    if args.selftest:
        selftest(config)
        return

    problems = config.validate()
    if problems:
        for p in problems:
            print(f"❌ {p}")
        sys.exit(1)

    print(f"[启动] 人设: {config.persona or '(默认角色卡)'}")
    print(f"[启动] LLM: {config.llm_provider}/{config.llm_model}")
    print(f"[启动] 输出: {config.chatbox_channel} 通道"
          + (f" ({config.osc_host}:{config.osc_port})" if config.chatbox_channel == "osc" else ""))
    if config.trigger_mode == "both":
        print(f"[启动] 触发: 双通道（auto 监听 + 按住 [{config.record_hotkey}] 说话）")
        print(f"        VRChat 里任何人说话自动回复；你按住 {config.record_hotkey} 可随时插话")
    elif config.trigger_mode == "auto":
        print(f"[启动] 触发: 自动监听模式（loopback 捕获 VRChat 输出，公共 AI）")
        print(f"        VRChat 里任何人说话都会触发回复；先跑 tools/probe_audio.py 验证捕获")
    else:
        print(f"[启动] 触发: 按住 [{config.record_hotkey}] 说话（私人模式）")
    print()

    Application(config).run()


if __name__ == "__main__":
    main()
