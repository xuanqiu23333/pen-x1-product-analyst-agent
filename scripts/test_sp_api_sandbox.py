"""Run one hosted Amazon Orders static sandbox call without exposing tokens or PII."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'backend'))

from dotenv import load_dotenv

from app.services.amazon_auth import AmazonAuth, AmazonAuthError, AmazonSettings
from app.services.amazon_orders import AmazonOrdersSandbox
from app.services.amazon_sp_api_client import AmazonAPIError, AmazonSPAPIClient


def run_smoke(settings: AmazonSettings, auth: AmazonAuth | None = None,
              client: AmazonSPAPIClient | None = None,
              emit: Callable[[str], None] = print):
    settings.require_credentials()
    settings.require_sandbox()
    emit('[SP-API] 环境：Sandbox')
    emit('[SP-API] 区域：北美')
    emit(f'[SP-API] Marketplace：{settings.marketplace_id}')
    auth = auth or AmazonAuth(
        settings.client_id, settings.client_secret, settings.refresh_token,
        token_url=settings.lwa_token_url, timeout=settings.timeout,
        refresh_buffer_seconds=settings.token_refresh_buffer_seconds,
    )
    auth.get_access_token()
    emit('[SP-API] LWA 令牌已获取')
    client = client or AmazonSPAPIClient(
        auth, endpoint=settings.api_endpoint, timeout=settings.timeout,
        max_retries=settings.max_retries,
    )
    order = AmazonOrdersSandbox(client).get_order()
    if order.marketplace_id != settings.marketplace_id:
        raise ValueError('Sandbox 订单 Marketplace 与配置不一致。')
    emit('[SP-API] Orders Sandbox 请求成功（HTTP 200）')
    emit(f'[SP-API] 订单记录数：1；订单 ID：{order.amazon_order_id}；状态：{order.order_status or "未知"}；下单时间：{order.purchase_date or "未知"}')
    emit('[SP-API] 冒烟测试通过')
    return order


def main() -> int:
    load_dotenv(PROJECT_ROOT / '.env', override=False)
    try:
        run_smoke(AmazonSettings.from_environment())
    except AmazonAuthError as error:
        print(f'[SP-API] LWA／配置失败：{error}', file=sys.stderr)
        return 1
    except AmazonAPIError as error:
        print(f'[SP-API] Orders 请求失败：HTTP {error.status_code}；错误码 {error.code or "未知"}；请求 ID {error.request_id or "无"}；{error.message}',
              file=sys.stderr)
        return 1
    except ValueError as error:
        print(f'[SP-API] Sandbox 配置或响应失败：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
