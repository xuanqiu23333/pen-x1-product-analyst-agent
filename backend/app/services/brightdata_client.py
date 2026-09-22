"""Bounded Bright Data Web Scraper API client for asynchronous snapshots."""

from __future__ import annotations

import os
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class BrightDataSettings:
    api_token: str = field(default='', repr=False)
    dataset_id: str = 'gd_le8e811kzy4ggddlq'
    review_target_per_product: int = 100
    timeout: float = 60.0
    poll_interval_seconds: float = 5.0
    max_poll_seconds: float = 180.0
    max_retries: int = 3
    schema_confirmed: bool = False

    @classmethod
    def from_environment(cls) -> 'BrightDataSettings':
        load_dotenv()
        return cls(
            api_token=os.getenv('BRIGHTDATA_API_TOKEN', '').strip(),
            dataset_id=os.getenv('BRIGHTDATA_AMAZON_REVIEWS_DATASET_ID', cls.dataset_id).strip(),
            review_target_per_product=int(os.getenv('BRIGHTDATA_REVIEW_TARGET_PER_PRODUCT', '100')),
            timeout=float(os.getenv('BRIGHTDATA_API_TIMEOUT', '60')),
            poll_interval_seconds=float(os.getenv('BRIGHTDATA_POLL_INTERVAL_SECONDS', '5')),
            max_poll_seconds=float(os.getenv('BRIGHTDATA_MAX_POLL_SECONDS', '180')),
            max_retries=int(os.getenv('BRIGHTDATA_MAX_RETRIES', '3')),
            schema_confirmed=os.getenv('BRIGHTDATA_SCHEMA_CONFIRMED', 'false').lower() == 'true',
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_token and self.dataset_id)


class BrightDataAPIError(Exception):
    def __init__(self, status_code: int | None, message: str, retryable: bool,
                 snapshot_id: str | None = None, *, error_code: str | None = None,
                 error_message: str | None = None, response_excerpt: str = ''):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.retryable = retryable
        self.snapshot_id = snapshot_id
        self.error_code = error_code
        self.error_message = error_message or message
        self.response_excerpt = response_excerpt[:2000]


class BrightDataClient:
    BASE_URL = 'https://api.brightdata.com'
    RETRYABLE_STATUS_CODES = {429, 500, 503}

    def __init__(self, settings: BrightDataSettings, http_client: httpx.Client | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        self.settings = settings
        self._http = http_client or httpx.Client(base_url=self.BASE_URL, timeout=settings.timeout)
        self._sleep = sleep
        self._monotonic = monotonic

    @property
    def _headers(self) -> dict[str, str]:
        return {'Authorization': f'Bearer {self.settings.api_token}',
                'Content-Type': 'application/json'}

    def _redact_text(self, value: object) -> str:
        text = str(value or '')
        if self.settings.api_token:
            text = text.replace(self.settings.api_token, '[REDACTED]')
        text = re.sub(
            r'(?i)(authorization\s*[:=]\s*)([^;,\r\n}]+)',
            lambda match: f'{match.group(1)}[REDACTED]', text,
        )
        text = re.sub(
            r'(?i)(api[_ -]?token\s*[:=]\s*)([^;,\r\n}]+)',
            lambda match: f'{match.group(1)}[REDACTED]', text,
        )
        return re.sub(r'(?i)bearer\s+[^\s;,}"\']+', 'Bearer [REDACTED]', text)

    def _sanitize_payload(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized = {}
            for key, item in value.items():
                normalized = re.sub(r'[^a-z]', '', str(key).lower())
                if any(secret in normalized for secret in (
                    'authorization', 'apitoken', 'accesstoken', 'refreshtoken',
                    'clientsecret', 'password',
                )) or normalized in {'user', 'email', 'ip'}:
                    sanitized[key] = '[REDACTED]'
                else:
                    sanitized[key] = self._sanitize_payload(item)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_payload(item) for item in value]
        if isinstance(value, str):
            return self._redact_text(value)
        return value

    def _safe_error_details(self, response: httpx.Response) -> tuple[str | None, str, str]:
        payload = None
        try:
            payload = response.json()
        except ValueError:
            pass
        error_code = None
        error_message = ''
        if isinstance(payload, dict):
            nested_error = payload.get('error')
            error_code = payload.get('error_code') or payload.get('code')
            error_message = payload.get('error_message') or payload.get('message') or ''
            if isinstance(nested_error, dict):
                error_code = error_code or nested_error.get('error_code') or nested_error.get('code')
                error_message = error_message or nested_error.get('message') or ''
            elif nested_error and not error_message:
                error_message = str(nested_error)
            safe_payload = self._sanitize_payload(payload)
            excerpt = json.dumps(safe_payload, ensure_ascii=False, default=str)
        else:
            excerpt = self._redact_text(response.text)
        safe_code = self._redact_text(error_code) if error_code is not None else None
        safe_message = self._redact_text(error_message) if error_message else (
            f'Bright Data API 请求失败（HTTP {response.status_code}）'
        )
        return safe_code, safe_message, excerpt[:2000]

    def _safe_message(self, response: httpx.Response) -> str:
        return self._safe_error_details(response)[1]

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = self._http.request(
                    method, path, headers=self._headers, timeout=self.settings.timeout, **kwargs
                )
            except httpx.HTTPError as error:
                if attempt >= self.settings.max_retries:
                    raise BrightDataAPIError(None, 'Bright Data API 网络请求失败。', True) from error
                self._sleep(2 ** attempt)
                continue
            if 200 <= response.status_code < 300:
                return response
            retryable = response.status_code in self.RETRYABLE_STATUS_CODES
            if retryable and attempt < self.settings.max_retries:
                self._sleep(2 ** attempt)
                continue
            error_code, error_message, response_excerpt = self._safe_error_details(response)
            raise BrightDataAPIError(
                response.status_code, error_message, retryable,
                error_code=error_code, error_message=error_message,
                response_excerpt=response_excerpt,
            )
        raise BrightDataAPIError(None, 'Bright Data API 请求失败。', True)

    def trigger_collection(self, inputs: list[dict]) -> str:
        response = self._request(
            'POST', '/datasets/v3/trigger',
            params={'dataset_id': self.settings.dataset_id, 'format': 'json',
                    'uncompressed_webhook': 'true'},
            json=inputs,
        )
        try:
            payload = response.json()
            snapshot_id = payload.get('snapshot_id') if isinstance(payload, dict) else None
        except ValueError:
            snapshot_id = None
        if not snapshot_id:
            raise BrightDataAPIError(response.status_code, 'Bright Data 未返回 snapshot_id。', False)
        return str(snapshot_id)

    def get_snapshot_status(self, snapshot_id: str) -> dict:
        response = self._request('GET', f'/datasets/v3/progress/{snapshot_id}')
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if not isinstance(payload, dict) or not payload.get('status'):
            raise BrightDataAPIError(response.status_code, 'Bright Data 快照状态格式无效。', False,
                                     snapshot_id)
        return payload

    def download_snapshot(self, snapshot_id: str) -> list[dict]:
        response = self._request(
            'GET', f'/datasets/v3/snapshot/{snapshot_id}', params={'format': 'json'}
        )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
            return payload
        if isinstance(payload, dict):
            for key in ('data', 'results'):
                rows = payload.get(key)
                if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
                    return rows
        raise BrightDataAPIError(response.status_code, 'Bright Data 快照数据格式无效。', False,
                                 snapshot_id)

    def collect(self, inputs: list[dict]) -> tuple[str, list[dict]]:
        snapshot_id = self.trigger_collection(inputs)
        started = self._monotonic()
        while True:
            payload = self.get_snapshot_status(snapshot_id)
            status = str(payload['status']).lower()
            if status == 'ready':
                return snapshot_id, self.download_snapshot(snapshot_id)
            if status in {'failed', 'canceled'}:
                message = str(payload.get('error_message') or f'Bright Data 快照状态为 {status}。')
                if self.settings.api_token:
                    message = message.replace(self.settings.api_token, '[REDACTED]')
                raise BrightDataAPIError(None, message, False, snapshot_id)
            if status not in {'starting', 'running'}:
                raise BrightDataAPIError(None, 'Bright Data 快照状态无效。', False, snapshot_id)
            if self._monotonic() - started >= self.settings.max_poll_seconds:
                raise BrightDataAPIError(None, 'TIMEOUT：Bright Data 快照轮询超时。', True,
                                         snapshot_id)
            self._sleep(self.settings.poll_interval_seconds)
