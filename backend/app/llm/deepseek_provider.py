import json
import re
import urllib.error
import urllib.request


def _sanitize(value: object, secret: str | None = None, limit: int = 1000) -> str:
    text = str(value or '')
    if secret:
        text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'(?i)bearer\s+[^\s,}"\]]+', 'Bearer [REDACTED]', text)
    text = re.sub(
        r'(?i)(authorization|api[_ -]?(?:token|key))\s*[:=]\s*[^\s,}"\]]+',
        r'\1=[REDACTED]', text,
    )
    return text[:limit]


class DeepSeekError(RuntimeError):
    def __init__(self, message: str, *, failure_stage: str, status_code: int | None = None,
                 error_code: str | None = None, response_excerpt: str | None = None):
        self.failure_stage = failure_stage
        self.status_code = status_code
        self.error_code = error_code
        self.safe_message = message
        self.response_excerpt = response_excerpt
        super().__init__(message)


class DeepSeekRequestError(DeepSeekError):
    pass


class DeepSeekResponseError(DeepSeekError):
    pass


class DeepSeekJSONError(DeepSeekError):
    pass


class DeepSeekProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def complete_json(self, task: str, payload: dict) -> dict:
        body = json.dumps({
            'model': self.model,
            'messages': [{'role': 'user', 'content': f'{task}\n{json.dumps(payload, ensure_ascii=False)}'}],
            'response_format': {'type': 'json_object'},
        }, ensure_ascii=False).encode()
        request = urllib.request.Request(
            'https://api.deepseek.com/chat/completions', data=body,
            headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as error:
            raw = error.read().decode('utf-8', errors='replace')
            error_code = None
            message = f'DeepSeek HTTP {error.code}'
            try:
                parsed = json.loads(raw)
                detail = parsed.get('error', parsed) if isinstance(parsed, dict) else {}
                if isinstance(detail, dict):
                    error_code = str(detail.get('code') or '') or None
                    message = str(detail.get('message') or message)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            raise DeepSeekRequestError(
                _sanitize(message, self.api_key), failure_stage='HTTP_REQUEST',
                status_code=error.code, error_code=error_code,
                response_excerpt=_sanitize(raw, self.api_key),
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise DeepSeekRequestError(
                _sanitize(str(error), self.api_key), failure_stage='HTTP_REQUEST',
            ) from error
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as error:
            raise DeepSeekResponseError(
                'DeepSeek HTTP 响应不是合法 JSON。', failure_stage='HTTP_RESPONSE_PARSE',
                response_excerpt=_sanitize(raw, self.api_key),
            ) from error
        try:
            content = envelope['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as error:
            raise DeepSeekResponseError(
                'DeepSeek 响应缺少 choices[0].message.content。',
                failure_stage='HTTP_RESPONSE_PARSE',
                response_excerpt=_sanitize(raw, self.api_key),
            ) from error
        if not isinstance(content, str):
            raise DeepSeekResponseError(
                'DeepSeek message.content 不是字符串。', failure_stage='HTTP_RESPONSE_PARSE',
                response_excerpt=_sanitize(raw, self.api_key),
            )
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError as error:
            raise DeepSeekJSONError(
                'DeepSeek message.content 不是合法 JSON。',
                failure_stage='MODEL_CONTENT_JSON_PARSE',
                response_excerpt=_sanitize(content, self.api_key),
            ) from error
        if not isinstance(parsed_content, dict):
            raise DeepSeekJSONError(
                'DeepSeek message.content 必须是 JSON 对象。',
                failure_stage='MODEL_CONTENT_JSON_PARSE',
                response_excerpt=_sanitize(content, self.api_key),
            )
        return parsed_content
