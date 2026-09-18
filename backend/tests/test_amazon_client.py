import httpx
import pytest

from app.services.amazon_auth import AmazonAuth
from app.services.amazon_sp_api_client import AmazonAPIError, AmazonSPAPIClient


def test_lwa_token_is_reused_until_five_minute_refresh_margin():
    requests = []
    now = [0.0]

    def reply(request):
        requests.append(request)
        assert request.url.path == '/auth/o2/token'
        return httpx.Response(200, json={'access_token': 'private-token', 'expires_in': 3600})

    transport = httpx.MockTransport(reply)
    auth = AmazonAuth('id', 'secret', 'refresh', http=httpx.Client(transport=transport), clock=lambda: now[0])
    assert auth.get_access_token() == 'private-token'
    now[0] = 3299
    assert auth.get_access_token() == 'private-token'
    now[0] = 3300
    assert auth.get_access_token() == 'private-token'
    assert len(requests) == 2


def test_sp_api_sends_current_headers_and_retries_rate_limit_twice():
    seen = []

    def reply(request):
        seen.append(request)
        if len(seen) < 3:
            return httpx.Response(429, headers={'x-amzn-RequestId': 'req-1', 'x-amzn-RateLimit-Limit': '0.5'})
        return httpx.Response(200, json={'asin': 'B000000001'}, headers={'x-amzn-RateLimit-Limit': '0.5'})

    class Auth:
        def get_access_token(self):
            return 'private-token'

    client = AmazonSPAPIClient(Auth(), endpoint='https://sandbox.sellingpartnerapi-na.amazon.com', http=httpx.Client(transport=httpx.MockTransport(reply)), sleep=lambda _: None)
    assert client.get('/catalog/2022-04-01/items/B000000001', 'getCatalogItem')['asin'] == 'B000000001'
    assert len(seen) == 3
    assert seen[0].headers['x-amz-access-token'] == 'private-token'
    assert seen[0].headers['user-agent'].startswith('PEN-X1/')
    assert seen[0].headers['x-amz-date'].endswith('Z')
    assert 'authorization' not in seen[0].headers
    assert client.api_requests == 3
    assert client.rate_limit_events == 2
    assert client.rate_limits['getCatalogItem'] == '0.5'


def test_unauthorized_is_not_retried_and_error_does_not_expose_secret():
    calls = []

    def reply(request):
        calls.append(request)
        return httpx.Response(401, json={'errors': [{'message': 'private-token secret refresh'}]}, headers={'x-amzn-RequestId': 'req-2'})

    class Auth:
        def get_access_token(self):
            return 'private-token'

    client = AmazonSPAPIClient(Auth(), http=httpx.Client(transport=httpx.MockTransport(reply)), sleep=lambda _: None)
    with pytest.raises(AmazonAPIError) as caught:
        client.get('/catalog/2022-04-01/items/B000000001', 'getCatalogItem')
    assert caught.value.status_code == 401
    assert caught.value.request_id == 'req-2'
    assert caught.value.retryable is False
    assert len(calls) == 1
    assert 'private-token' not in str(caught.value)
    assert 'refresh' not in str(caught.value)
