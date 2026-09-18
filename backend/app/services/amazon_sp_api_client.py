"""Shared SP-API transport with bounded retries and secret-safe errors."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.services.amazon_auth import AmazonAuth


class AmazonAPIError(Exception):
    def __init__(self, status_code: int, operation: str, message: str,
                 request_id: str | None = None, retryable: bool = False,
                 code: str | None = None):
        self.status_code = status_code
        self.operation = operation
        self.message = message
        self.request_id = request_id
        self.retryable = retryable
        self.code = code
        super().__init__(f'{operation}: {message} (HTTP {status_code})')


class AmazonSPAPIClient:
    def __init__(self, auth: AmazonAuth, endpoint: str = 'https://sellingpartnerapi-na.amazon.com',
                 http: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep,
                 timeout: float = 12, max_retries: int = 2):
        if max_retries < 0:
            raise ValueError('max_retries must be non-negative')
        self.auth = auth
        self.endpoint = endpoint.rstrip('/')
        self.http = http or httpx.Client(timeout=timeout)
        self.sleep = sleep
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_requests = 0
        self.api_errors = 0
        self.rate_limit_events = 0
        self.rate_limits: dict[str, str] = {}
        self.request_ids: list[str] = []

    def get(self, path: str, operation: str, params: dict | None = None) -> dict:
        return self.request('GET', path, params=params, operation=operation)

    def post(self, path: str, operation: str, payload: dict | None = None) -> dict:
        return self.request('POST', path, json=payload, operation=operation)

    def request(self, method: str, path: str, params: dict | None = None,
                json: dict | None = None, headers: dict | None = None,
                operation: str | None = None) -> dict:
        method = method.upper()
        if method not in ('GET', 'POST', 'PUT', 'DELETE'):
            raise ValueError('Unsupported SP-API method')
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('SP-API path must be relative to configured endpoint')
        operation = operation or f'{method} {path}'
        retry_count = 0
        refreshed_after_401 = False
        while True:
            token = self.auth.get_access_token()
            request_headers = {
                'x-amz-date': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                'user-agent': 'PEN-X1/1.0 (Language=Python/3.11)',
                'accept': 'application/json',
            }
            request_headers.update(headers or {})
            request_headers['x-amz-access-token'] = token
            self.api_requests += 1
            try:
                response = self.http.request(method, self.endpoint + path, params=params,
                                             json=json, headers=request_headers, timeout=self.timeout)
            except httpx.HTTPError:
                self.api_errors += 1
                if retry_count < self.max_retries:
                    self.sleep(2 ** retry_count)
                    retry_count += 1
                    continue
                raise AmazonAPIError(0, operation, 'Amazon 请求网络不可用。',
                                     retryable=True, code='NetworkError') from None

            request_id = response.headers.get('x-amzn-RequestId')
            if request_id:
                request_id = self._safe_text(request_id, token, None)
                if request_id:
                    self.request_ids.append(request_id)
            limit = response.headers.get('x-amzn-RateLimit-Limit')
            if limit:
                self.rate_limits[operation] = limit
            if 200 <= response.status_code < 300:
                if response.status_code == 204:
                    return {}
                try:
                    return response.json()
                except ValueError:
                    self.api_errors += 1
                    raise AmazonAPIError(response.status_code, operation,
                                         'Amazon 响应不是有效 JSON。', request_id,
                                         code='InvalidResponse') from None

            self.api_errors += 1
            if response.status_code == 429:
                self.rate_limit_events += 1
            if response.status_code == 401 and not refreshed_after_401:
                # Legacy injected doubles without force_refresh cannot refresh.
                try:
                    self.auth.get_access_token(force_refresh=True)
                except TypeError:
                    pass
                else:
                    refreshed_after_401 = True
                    continue
            retryable = response.status_code in (429, 500, 503)
            if retryable and retry_count < self.max_retries:
                self.sleep(self._retry_delay(response, retry_count))
                retry_count += 1
                continue
            code, message = self._error_details(response, token)
            raise AmazonAPIError(response.status_code, operation, message, request_id,
                                 retryable, code) from None

    def _safe_text(self, value: str, token: str, fallback: str | None) -> str | None:
        secrets = (token, *getattr(self.auth, '_credentials', ()))
        if any(secret and secret in value for secret in secrets):
            return fallback
        if re.search(r'(?i)(Atza[|]|Atzr[|]|amzn1[.]oa2-cs|access.?token|refresh.?token|client.?secret)', value):
            return fallback
        return value[:500]

    def _error_details(self, response: httpx.Response, token: str) -> tuple[str, str]:
        messages = {400: '请求参数不合法。', 401: '认证无效或已过期。', 403: '当前应用无访问权限。',
                    404: '资源不存在。', 429: '达到 Amazon 请求限额。',
                    500: 'Amazon 服务内部错误。', 503: 'Amazon 服务暂不可用。'}
        fallback = messages.get(response.status_code, 'Amazon API 请求失败。')
        code = f'HTTP_{response.status_code}'
        try:
            payload: Any = response.json()
        except ValueError:
            return code, fallback
        errors = payload.get('errors') if isinstance(payload, dict) else None
        first = errors[0] if isinstance(errors, list) and errors else None
        if not isinstance(first, dict):
            return code, fallback
        safe_code = self._safe_text(str(first.get('code') or ''), token, None)
        safe_message = self._safe_text(str(first.get('message') or ''), token, None)
        return safe_code or code, safe_message or fallback

    @staticmethod
    def _retry_delay(response: httpx.Response, retry_count: int) -> float:
        if response.status_code == 429:
            value = response.headers.get('Retry-After')
            if value:
                try:
                    seconds = float(value)
                except ValueError:
                    try:
                        deadline = parsedate_to_datetime(value)
                        seconds = (deadline - datetime.now(timezone.utc)).total_seconds()
                    except (TypeError, ValueError, OverflowError):
                        seconds = -1
                if 0 <= seconds <= 30:
                    return seconds
        return float(2 ** retry_count)
