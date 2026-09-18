"""Login with Amazon token exchange; secrets never leave the request body."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv


class AmazonAuthError(Exception):
    pass


@dataclass(frozen=True)
class AmazonSettings:
    client_id: str = field(default='', repr=False)
    client_secret: str = field(default='', repr=False)
    refresh_token: str = field(default='', repr=False)
    endpoint: str = 'https://sellingpartnerapi-na.amazon.com'
    marketplace_id: str = 'ATVPDKIKX0DER'
    mode: str = 'sandbox'
    real_data_enabled: bool = False
    region: str = 'na'
    lwa_token_url: str = 'https://api.amazon.com/auth/o2/token'
    marketplace_id_us: str = 'ATVPDKIKX0DER'
    marketplace_id_ca: str = 'A2EUQ1WTGCTBG2'
    timeout: float = 30
    max_retries: int = 3
    token_refresh_buffer_seconds: int = 300

    @classmethod
    def from_environment(cls) -> 'AmazonSettings':
        load_dotenv()
        def selected(primary: str, legacy: str | None, default: str) -> str:
            return os.getenv(primary) or (os.getenv(legacy) if legacy else None) or default

        return cls(
            client_id=selected('SP_API_LWA_CLIENT_ID', 'AMAZON_SP_API_CLIENT_ID', ''),
            client_secret=selected('SP_API_LWA_CLIENT_SECRET', 'AMAZON_SP_API_CLIENT_SECRET', ''),
            refresh_token=selected('SP_API_REFRESH_TOKEN', 'AMAZON_SP_API_REFRESH_TOKEN', ''),
            endpoint=selected('SP_API_ENDPOINT', 'AMAZON_SP_API_ENDPOINT', cls.endpoint),
            marketplace_id=selected('SP_API_DEFAULT_MARKETPLACE_ID', 'AMAZON_MARKETPLACE_ID', cls.marketplace_id),
            mode=selected('SP_API_ENV', 'AMAZON_SP_API_MODE', 'sandbox').lower(),
            real_data_enabled=os.getenv('AMAZON_REAL_DATA_ENABLED', 'false').lower() == 'true',
            region=selected('SP_API_REGION', None, 'na').lower(),
            lwa_token_url=selected('SP_API_LWA_TOKEN_URL', None, cls.lwa_token_url),
            marketplace_id_us=selected('SP_API_MARKETPLACE_ID_US', None, cls.marketplace_id_us),
            marketplace_id_ca=selected('SP_API_MARKETPLACE_ID_CA', None, cls.marketplace_id_ca),
            timeout=float(selected('SP_API_TIMEOUT', None, '30')),
            max_retries=int(selected('SP_API_MAX_RETRIES', None, '3')),
            token_refresh_buffer_seconds=int(selected('SP_API_TOKEN_REFRESH_BUFFER_SECONDS', None, '300')),
        )

    @property
    def configured(self) -> bool:
        return all((self.client_id, self.client_secret, self.refresh_token))

    def require_credentials(self) -> None:
        if not self.configured:
            raise AmazonAuthError('Amazon SP-API credentials are incomplete')

    def require_sandbox(self) -> None:
        if (self.mode != 'sandbox' or self.region != 'na' or
                self.api_endpoint != 'https://sandbox.sellingpartnerapi-na.amazon.com' or
                self.lwa_token_url != 'https://api.amazon.com/auth/o2/token'):
            raise ValueError('Sandbox 冒烟仅允许 Amazon 北美沙箱端点与官方 LWA 端点。')

    @property
    def api_endpoint(self) -> str:
        if self.mode == 'sandbox':
            return self.endpoint.replace('https://sellingpartnerapi-', 'https://sandbox.sellingpartnerapi-', 1)
        return self.endpoint


class AmazonAuth:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str,
                 http: httpx.Client | None = None, clock: Callable[[], float] = time.monotonic,
                 token_url: str = 'https://api.amazon.com/auth/o2/token', timeout: float = 12,
                 refresh_buffer_seconds: int = 300):
        self._credentials = (client_id, client_secret, refresh_token)
        self._http = http or httpx.Client(timeout=timeout)
        self._clock = clock
        self._token_url = token_url
        self._timeout = timeout
        self._refresh_buffer_seconds = refresh_buffer_seconds
        self._token: str | None = None
        self._expires_at = 0.0
        self.expires_in = 0
        self._lock = threading.Lock()

    @property
    def expires_at(self) -> float:
        return self._expires_at

    def get_access_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            if not force_refresh and self._token and self._expires_at - self._clock() > self._refresh_buffer_seconds:
                return self._token
            client_id, client_secret, refresh_token = self._credentials
            if not all(self._credentials):
                raise AmazonAuthError('Amazon SP-API credentials are incomplete')
            try:
                response = self._http.post(
                    self._token_url,
                    data={'grant_type': 'refresh_token', 'refresh_token': refresh_token,
                          'client_id': client_id, 'client_secret': client_secret}, timeout=self._timeout,
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
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                raise AmazonAuthError('Amazon 认证响应不可用。') from None
            self._token = token
            self.expires_in = expires_in
            self._expires_at = self._clock() + expires_in
            return token


TokenManager = AmazonAuth
