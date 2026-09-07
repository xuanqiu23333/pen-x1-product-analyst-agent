import os
from .mock_provider import MockLLMProvider

def get_llm_provider():
    if os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("DEEPSEEK_API_KEY"):
        return MockLLMProvider()
    from .deepseek_provider import DeepSeekProvider
    return DeepSeekProvider(os.environ["DEEPSEEK_API_KEY"], os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
