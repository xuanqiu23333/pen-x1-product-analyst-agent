class MockLLMProvider:
    def complete_json(self, task: str, payload: dict) -> dict:
        return {"mode":"DEMO_MODE", "task":task, "result":payload}
