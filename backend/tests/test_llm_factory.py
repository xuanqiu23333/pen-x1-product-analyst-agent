from app.llm.deepseek_provider import DeepSeekProvider
from app.llm.mock_provider import MockLLMProvider
from app.llm.factory import get_llm_provider

def test_force_real_mode_chooses_deepseek_when_key_exists(monkeypatch):
    monkeypatch.setenv('DEMO_MODE','true')
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-key')
    assert isinstance(get_llm_provider(force_real=True), DeepSeekProvider)

def test_demo_mode_uses_mock_provider(monkeypatch):
    monkeypatch.setenv('DEMO_MODE','true')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    assert isinstance(get_llm_provider(), MockLLMProvider)

def test_real_mode_without_key_does_not_get_mock_provider(monkeypatch):
    monkeypatch.setattr('app.llm.factory.load_dotenv', lambda: None)
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    assert get_llm_provider(force_real=True) is None
