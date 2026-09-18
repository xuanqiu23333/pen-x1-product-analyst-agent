import httpx
import pytest

from app.services.amazon_auth import AmazonAuth, AmazonAuthError, AmazonSettings


def test_new_sp_api_environment_names_take_precedence_without_exposing_secrets(monkeypatch):
    monkeypatch.setenv('AMAZON_SP_API_CLIENT_ID', 'old-id')
    monkeypatch.setenv('AMAZON_SP_API_CLIENT_SECRET', 'old-secret')
    monkeypatch.setenv('AMAZON_SP_API_REFRESH_TOKEN', 'old-refresh')
    monkeypatch.setenv('SP_API_LWA_CLIENT_ID', 'new-id')
    monkeypatch.setenv('SP_API_LWA_CLIENT_SECRET', 'new-secret')
    monkeypatch.setenv('SP_API_REFRESH_TOKEN', 'new-refresh')
    monkeypatch.setenv('SP_API_ENV', 'sandbox')
    monkeypatch.setenv('SP_API_ENDPOINT', 'https://sandbox.sellingpartnerapi-na.amazon.com')
    monkeypatch.setenv('SP_API_TIMEOUT', '30')
    monkeypatch.setenv('SP_API_MAX_RETRIES', '3')
    settings = AmazonSettings.from_environment()
    assert settings.client_id == 'new-id'
    assert settings.client_secret == 'new-secret'
    assert settings.refresh_token == 'new-refresh'
    assert settings.api_endpoint == 'https://sandbox.sellingpartnerapi-na.amazon.com'
    assert settings.timeout == 30
    assert settings.max_retries == 3
    assert 'new-secret' not in repr(settings)
    assert 'new-refresh' not in repr(settings)


def test_missing_credentials_are_strict_for_smoke_but_do_not_prevent_web_fallback():
    settings = AmazonSettings()
    assert settings.configured is False
    with pytest.raises(AmazonAuthError, match='Amazon SP-API credentials are incomplete'):
        settings.require_credentials()


def test_token_cache_respects_configured_buffer_and_force_refreshes_once():
    calls = []
    now = [0.0]

    def reply(request):
        calls.append(request)
        return httpx.Response(200, json={'access_token': f'token-{len(calls)}', 'expires_in': 3600})

    auth = AmazonAuth('id', 'secret', 'refresh', http=httpx.Client(transport=httpx.MockTransport(reply)),
                      clock=lambda: now[0], refresh_buffer_seconds=600, timeout=30)
    assert auth.get_access_token() == 'token-1'
    now[0] = 2999
    assert auth.get_access_token() == 'token-1'
    now[0] = 3000
    assert auth.get_access_token() == 'token-2'
    assert auth.get_access_token(force_refresh=True) == 'token-3'
    assert auth.expires_in == 3600
    assert len(calls) == 3


def test_incomplete_auth_fails_before_any_http_request():
    def never(_):
        raise AssertionError('network must not be called')

    auth = AmazonAuth('id', '', 'refresh', http=httpx.Client(transport=httpx.MockTransport(never)))
    with pytest.raises(AmazonAuthError, match='Amazon SP-API credentials are incomplete'):
        auth.get_access_token()
