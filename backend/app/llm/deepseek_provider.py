import json
import urllib.request
class DeepSeekProvider:
    def __init__(self, api_key: str, model: str): self.api_key, self.model = api_key, model
    def complete_json(self, task: str, payload: dict) -> dict:
        body = json.dumps({"model":self.model,"messages":[{"role":"user","content":f"{task}\n{json.dumps(payload)}"}],"response_format":{"type":"json_object"}}).encode()
        request = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body, headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(json.loads(response.read())["choices"][0]["message"]["content"])
