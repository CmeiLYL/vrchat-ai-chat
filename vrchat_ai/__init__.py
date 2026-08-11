"""VRChat AI 聊天：分层架构包。

domain         领域层（纯数据/事件，零外部依赖）
interfaces     抽象层（ABC 接口，依赖倒置核心）
infrastructure 实现层（OSC/whisper/LLM/热键 具体策略）
application    应用层（门面/人设/管道 编排）
factories      简单工厂（按配置装配策略）
event_bus      事件总线（观察者模式）
"""
