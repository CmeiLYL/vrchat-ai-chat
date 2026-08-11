"""配置加载与校验。"""
from config import AppConfig, load_config


def test_load_config_returns_appconfig(config):
    assert isinstance(config, AppConfig)


def test_deepseek_without_key_reports_problem(config):
    # 显式构造无 Key 配置（不依赖 .env 实际状态）
    cfg = config.__class__(**{**config.__dict__, "llm_api_key": ""})
    problems = cfg.validate()
    assert any("LLM_API_KEY" in p for p in problems)


def test_mock_mode_validates_clean(mock_config):
    assert mock_config.validate() == []


def test_ollama_requires_base_url(config):
    cfg = config.__class__(**{**config.__dict__, "llm_provider": "ollama",
                              "llm_base_url": ""})
    problems = cfg.validate()
    assert any("LLM_BASE_URL" in p for p in problems)


def test_both_mode_valid(config):
    cfg = config.__class__(**{**config.__dict__, "trigger_mode": "both",
                              "llm_api_key": "sk-x"})
    assert all("TRIGGER_MODE" not in p for p in cfg.validate())


def test_env_override_applies(config, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    assert load_config().llm_model == "gpt-4o-mini"
