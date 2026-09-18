"""Small read-only SP-API transport with bounded retry and safe errors."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx

from app.services.amazon_auth import AmazonAuth


class AmazonAPIError(Exception):
    def __init__(self, status_code: int, operation: str, message: str,
                 request_id: str | None = None, retryable: bool = False):
        self.status_code = status_code
        self.operation = operation
        self.message = message
        self.request_id = request_id
        self.retryable = retryable
        super().__init__(f'{operation}: {message} (HTTP {status_code})')


class AmazonSPAPIClient:
    def __init__(self, auth: AmazonAuth, endpoint: str = 'https://sellingpartnerapi-na.amazon.com',
                 http: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep,
                 timeout: float = 12):
        self.auth = auth
        self.endpoint = endpoint.rstrip('/')
        self.http = http or httpx.Client(timeout=timeout)
        self.sleep = sleep
        self.timeout = timeout
        self.api_requests = 0
        self.api_errors = 0
        self.rate_limit_events = 0
        self.rate_limits: dict[str, str] = {}
        self.request_ids: list[str] = []

    def get(self, path: str, operation: str, params: dict | None = None) -> dict:
        return self._request('GET', path, operation, params=params)

    def post(self, path: str, operation: str, payload: dict | None = None) -> dict:
        return self._request('POST', path, operation, payload=payload)

    def _request(self, method: str, path: str, operation: str,
                 params: dict | None = None, payload: dict | None = None) -> dict:
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('SP-API path must be relative to configured endpoint')
        for attempt in range(3):
            headers = {
                'x-amz-access-token': self.auth.get_access_token(),
                'x-amz-date': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                'user-agent': 'PEN-X1/1.0 (Language=Python/3.11)',
                'accept': 'application/json',
            }
            self.api_requests += 1
            try:
                response = self.http.request(method, self.endpoint + path, params=params,
                                             json=payload, headers=headers, timeout=self.timeout)
            except httpx.HTTPError:
                self.api_errors += 1
                if attempt < 2:
                    self.sleep(2 ** attempt)
                    continue
                raise AmazonAPIError(0, operation, 'Amazon 请求网络不可用。', retryable=True) from None
            request_id = response.headers.get('x-amzn-RequestId')
            if request_id:
                self.request_ids.append(request_id)
            limit = response.headers.get('x-amzn-RateLimit-Limit')
            if limit:
                self.rate_limits[operation] = limit
            if response.status_code in (200, 204):
                if response.status_code == 204:
                    return {}
                try:
                    return response.json()
                except ValueError:
                    self.api_errors += 1
                    raise AmazonAPIError(200, operation, 'Amazon 响应不是有效 JSON。', request_id) from None
            self.api_errors += 1
            if response.status_code == 429:
                self.rate_limit_events += 1
            retryable = response.status_code in (429, 500, 503)
            if retryable and attempt < 2:
                self.sleep(2 ** attempt)
                continue
            messages = {400: '请求参数不合法。', 401: '认证无效或已过期。', 403: '当前应用无访问权限。',
                        404: '资源不存在。', 429: '达到 Amazon 请求限额。',
                        500: 'Amazon 服务内部错误。', 503: 'Amazon 服务暂不可用。'}
            raise AmazonAPIError(response.status_code, operation,
                                 messages.get(response.status_code, 'Amazon API 请求失败。'),
                                 request_id, retryable) from None
        raise AssertionError('bounded retry loop exhausted')
