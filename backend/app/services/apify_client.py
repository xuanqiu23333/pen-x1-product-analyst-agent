"""Bounded Apify Actor client for Amazon review dataset collection."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class ApifySettings:
    api_token: str = field(default='', repr=False)
    actor: str = 'kestrel/amazon-reviews-scraper'
    base_url: str = 'https://api.apify.com/v2'
    review_target_per_product: int = 100
    timeout: float = 60.0
    poll_interval_seconds: float = 5.0
    max_poll_seconds: float = 180.0

    @classmethod
    def from_environment(cls) -> 'ApifySettings':
        load_dotenv()
        return cls(
            api_token=os.getenv('APIFY_API_TOKEN', '').strip(),
            actor=os.getenv('APIFY_AMAZON_REVIEWS_ACTOR', cls.actor).strip(),
            base_url=os.getenv('APIFY_API_BASE_URL', cls.base_url).strip().rstrip('/'),
            review_target_per_product=int(os.getenv('APIFY_REVIEW_TARGET_PER_PRODUCT', '100')),
            timeout=float(os.getenv('APIFY_API_TIMEOUT', '60')),
            poll_interval_seconds=float(os.getenv('APIFY_POLL_INTERVAL_SECONDS', '5')),
            max_poll_seconds=float(os.getenv('APIFY_MAX_POLL_SECONDS', '180')),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_token and self.actor and self.base_url)


class ApifyAPIError(Exception):
    def __init__(self, status_code: int | None, message: str, retryable: bool,
                 actor_run_id: str | None = None, *, error_code: str | None = None,
                 response_excerpt: str = ''):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.retryable = retryable
        self.actor_run_id = actor_run_id
        self.error_code = error_code
        self.response_excerpt = response_excerpt[:2000]


class ApifyClient:
    ACTIVE_STATUSES = {'READY', 'RUNNING'}
    FAILURE_STATUSES = {'FAILED', 'TIMED-OUT', 'ABORTED'}

    def __init__(self, settings: ApifySettings, http_client: httpx.Client | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        self.settings = settings
        self._http = http_client or httpx.Client(
            base_url=f'{settings.base_url.rstrip("/")}/', timeout=settings.timeout
        )
        self._sleep = sleep
        self._monotonic = monotonic

    @property
    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self.settings.api_token}',
            'Content-Type': 'application/json',
        }

    def _redact(self, value: object) -> str:
        text = str(value or '')
        if self.settings.api_token:
            text = text.replace(self.settings.api_token, '[REDACTED]')
        return text

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http.request(
                method, path.lstrip('/'), headers=self._headers,
                timeout=self.settings.timeout, **kwargs,
            )
        except httpx.HTTPError as error:
            raise ApifyAPIError(None, 'Apify API 网络请求失败。', True) from error
        if 200 <= response.status_code < 300:
            return response
        error_code = None
        message = f'Apify API 请求失败（HTTP {response.status_code}）'
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            error = payload.get('error')
            if isinstance(error, dict):
                error_code = self._redact(error.get('type') or error.get('code')) or None
                message = self._redact(error.get('message') or message)
            excerpt = json.dumps(payload, ensure_ascii=False, default=str)
        else:
            excerpt = response.text
        excerpt = self._redact(excerpt)[:2000]
        raise ApifyAPIError(
            response.status_code, message,
            response.status_code in {429, 500, 502, 503, 504},
            error_code=error_code, response_excerpt=excerpt,
        )

    @staticmethod
    def _unwrap_data(response: httpx.Response, label: str) -> dict:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        data = payload.get('data') if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ApifyAPIError(response.status_code, f'Apify {label} 响应格式无效。', False)
        return data

    def start_actor(self, actor_input: dict) -> dict:
        if not self.settings.configured:
            raise ApifyAPIError(None, 'APIFY_NOT_CONFIGURED', False)
        actor_id = self.settings.actor.replace('/', '~')
        response = self._request('POST', f'actors/{actor_id}/runs', json=actor_input)
        data = self._unwrap_data(response, 'Actor run')
        if not data.get('id') or not data.get('status'):
            raise ApifyAPIError(response.status_code, 'Apify Actor run 缺少 id 或 status。', False)
        return data

    def get_run(self, actor_run_id: str) -> dict:
        response = self._request('GET', f'actor-runs/{actor_run_id}')
        data = self._unwrap_data(response, 'run status')
        if not data.get('status'):
            raise ApifyAPIError(response.status_code, 'Apify run 缺少 status。', False,
                                actor_run_id)
        return data

    def wait_for_run(self, actor_run_id: str) -> dict:
        started = self._monotonic()
        while True:
            run = self.get_run(actor_run_id)
            status = str(run['status']).upper()
            if status == 'SUCCEEDED':
                return run
            if status in self.FAILURE_STATUSES:
                raise ApifyAPIError(None, f'Apify Actor run 状态为 {status}。', False,
                                    actor_run_id)
            if status not in self.ACTIVE_STATUSES:
                raise ApifyAPIError(None, f'Apify Actor run 状态无效：{status}。', False,
                                    actor_run_id)
            if self._monotonic() - started >= self.settings.max_poll_seconds:
                raise ApifyAPIError(None, 'TIMEOUT：Apify Actor run 轮询超时。', True,
                                    actor_run_id)
            self._sleep(self.settings.poll_interval_seconds)

    def get_dataset_items(self, dataset_id: str) -> list[dict]:
        response = self._request(
            'GET', f'datasets/{dataset_id}/items', params={'clean': 'true'}
        )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
            return payload
        raise ApifyAPIError(response.status_code, 'Apify Dataset items 格式无效。', False)

    def collect(self, actor_input: dict) -> dict:
        started = self.start_actor(actor_input)
        actor_run_id = str(started['id'])
        run = self.wait_for_run(actor_run_id)
        dataset_id = run.get('defaultDatasetId')
        if not dataset_id:
            raise ApifyAPIError(None, 'Apify SUCCEEDED run 缺少 defaultDatasetId。', False,
                                actor_run_id)
        return {
            'actor_run_id': actor_run_id,
            'dataset_id': str(dataset_id),
            'status': 'SUCCEEDED',
            'items': self.get_dataset_items(str(dataset_id)),
        }
