import os
from dotenv import load_dotenv
from .mock_provider import MockLLMProvider

def get_llm_provider(force_real: bool = False):
    load_dotenv()
    api_key=os.getenv('DEEPSEEK_API_KEY')
    if (not force_real and os.getenv('DEMO_MODE','true').lower()=='true') or not api_key:
        return MockLLMProvider()
    from .deepseek_provider import DeepSeekProvider
    return DeepSeekProvider(api_key, os.getenv('DEEPSEEK_MODEL','deepseek-chat'))
