from app.llm.client import AnthropicLLM, OpenAILLM, make_llm


def _clear(monkeypatch):
    from app.config import get_settings
    for k in ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()


def test_default_is_anthropic(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    from app.config import get_settings
    get_settings.cache_clear()
    assert isinstance(make_llm(), AnthropicLLM)
    get_settings.cache_clear()


def test_only_openai_key_auto_selects_openai(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    from app.config import get_settings
    get_settings.cache_clear()
    assert isinstance(make_llm(), OpenAILLM)
    get_settings.cache_clear()


def test_explicit_provider_wins(monkeypatch):
    _clear(monkeypatch)
    # Ambas keys configuradas, pero LLM_PROVIDER manda.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    from app.config import get_settings
    get_settings.cache_clear()
    assert isinstance(make_llm(), OpenAILLM)
    get_settings.cache_clear()
