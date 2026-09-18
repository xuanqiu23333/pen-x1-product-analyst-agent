"""Login with Amazon token exchange; secrets never leave the request body."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv


class AmazonAuthError(Exception):
    pass


@dataclass(frozen=True)
class AmazonSettings:
    client_id: str = ''
    client_secret: str = ''
    refresh_token: str = ''
    endpoint: str = 'https://sellingpartnerapi-na.amazon.com'
    marketplace_id: str = 'ATVPDKIKX0DER'
    mode: str = 'sandbox'
    real_data_enabled: bool = False

    @classmethod
    def from_environment(cls) -> 'AmazonSettings':
        load_dotenv()
        return cls(
            client_id=os.getenv('AMAZON_SP_API_CLIENT_ID', ''),
            client_secret=os.getenv('AMAZON_SP_API_CLIENT_SECRET', ''),
            refresh_token=os.getenv('AMAZON_SP_API_REFRESH_TOKEN', ''),
            endpoint=os.getenv('AMAZON_SP_API_ENDPOINT', cls.endpoint),
            marketplace_id=os.getenv('AMAZON_MARKETPLACE_ID', cls.marketplace_id),
            mode=os.getenv('AMAZON_SP_API_MODE', 'sandbox').lower(),
            real_data_enabled=os.getenv('AMAZON_REAL_DATA_ENABLED', 'false').lower() == 'true',
        )

    @property
    def configured(self) -> bool:
        return all((self.client_id, self.client_secret, self.refresh_token))

    @property
    def api_endpoint(self) -> str:
        if self.mode == 'sandbox':
            return self.endpoint.replace('https://sellingpartnerapi-', 'https://sandbox.sellingpartnerapi-', 1)
        return self.endpoint


class AmazonAuth:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str,
                 http: httpx.Client | None = None, clock: Callable[[], float] = time.monotonic):
        self._credentials = (client_id, client_secret, refresh_token)
        self._http = http or httpx.Client(timeout=12)
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get_access_token(self) -> str:
        with self._lock:
            if self._token and self._expires_at - self._clock() > 300:
                return self._token
            client_id, client_secret, refresh_token = self._credentials
            if not all(self._credentials):
                raise AmazonAuthError('Amazon SP-API 凭证尚未配置。')
            try:
                response = self._http.post(
                    'https://api.amazon.com/auth/o2/token',
                    data={'grant_type': 'refresh_token', 'refresh_token': refresh_token,
                          'client_id': client_id, 'client_secret': client_secret}, timeout=12,
                )
                if response.status_code != 200:
                    raise AmazonAuthError(f'Amazon 认证失败（HTTP {response.status_code}）。')
                payload = response.json()
                token = payload['access_token']
                expires_in = int(payload['expires_in'])
                if not token or expires_in <= 0:
                    raise ValueError('invalid token response')
            except AmazonAuthError:
                raise
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                raise AmazonAuthError('Amazon 认证响应不可用。') from None
            self._token = token
            self._expires_at = self._clock() + expires_in
            return token
