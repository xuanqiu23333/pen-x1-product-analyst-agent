import httpx
import pytest

from app.services.amazon_auth import AmazonAuth
from app.services.amazon_sp_api_client import AmazonAPIError, AmazonSPAPIClient


def test_generic_request_supports_four_methods_without_header_token_override():
    seen = []

    def reply(request):
        seen.append(request)
        return httpx.Response(200, json={'method': request.method})

    class Auth:
        def get_access_token(self):
            return 'safe-test-token'

    client = AmazonSPAPIClient(Auth(), http=httpx.Client(transport=httpx.MockTransport(reply)))
    for method in ('GET', 'POST', 'PUT', 'DELETE'):
        result = client.request(method, '/test', json={'example': True} if method in ('POST', 'PUT') else None,
                                headers={'x-amz-access-token': 'wrong-token'})
        assert result == {'method': method}
    assert [request.method for request in seen] == ['GET', 'POST', 'PUT', 'DELETE']
    assert all(request.headers['x-amz-access-token'] == 'safe-test-token' for request in seen)


def test_first_401_forces_one_lwa_refresh_and_replays_original_request_once():
    seen_tokens = []
    lwa_calls = []

    def reply(request):
        if request.url.path == '/auth/o2/token':
            lwa_calls.append(request)
            return httpx.Response(200, json={'access_token': f'token-{len(lwa_calls)}', 'expires_in': 3600})
        seen_tokens.append(request.headers['x-amz-access-token'])
        return httpx.Response(401 if len(seen_tokens) == 1 else 200,
                              json={'errors': [{'code': 'Unauthorized', 'message': 'Expired token'}]}
                              if len(seen_tokens) == 1 else {'ok': True})

    http = httpx.Client(transport=httpx.MockTransport(reply))
    auth = AmazonAuth('id', 'test-secret', 'test-refresh', http=http)
    client = AmazonSPAPIClient(auth, http=http, sleep=lambda _: None)
    assert client.get('/test', 'getTest') == {'ok': True}
    assert seen_tokens == ['token-1', 'token-2']
    assert len(lwa_calls) == 2
    assert client.api_requests == 2


def test_second_401_stops_and_preserves_safe_amazon_error_fields():
    lwa_calls = []
    api_calls = []

    def reply(request):
        if request.url.path == '/auth/o2/token':
            lwa_calls.append(request)
            return httpx.Response(200, json={'access_token': f'token-{len(lwa_calls)}', 'expires_in': 3600})
        api_calls.append(request)
        return httpx.Response(401, json={'errors': [
            {'code': 'Unauthorized', 'message': f"Expired {request.headers['x-amz-access-token']}"}]},
            headers={'x-amzn-RequestId': 'request-123'})

    http = httpx.Client(transport=httpx.MockTransport(reply))
    client = AmazonSPAPIClient(AmazonAuth('id', 'test-secret', 'test-refresh', http=http),
                               http=http, sleep=lambda _: None)
    with pytest.raises(AmazonAPIError) as caught:
        client.get('/test', 'getTest')
    assert len(api_calls) == 2
    assert len(lwa_calls) == 2
    assert (caught.value.status_code, caught.value.code, caught.value.request_id) == (
        401, 'Unauthorized', 'request-123')
    assert 'token-1' not in str(caught.value)
    assert 'token-2' not in str(caught.value)
    assert 'test-secret' not in str(caught.value)
    assert 'test-refresh' not in str(caught.value)


def test_429_uses_retry_after_and_500_retries_are_bounded():
    sleeps = []
    calls = []

    class Auth:
        def get_access_token(self):
            return 'safe-test-token'

    def reply(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={'errors': [{'code': 'QuotaExceeded', 'message': 'Slow down'}]},
                                  headers={'Retry-After': '2.5'})
        return httpx.Response(500, json={'errors': [{'code': 'InternalFailure', 'message': 'Server error'}]})

    client = AmazonSPAPIClient(Auth(), http=httpx.Client(transport=httpx.MockTransport(reply)),
                               sleep=sleeps.append, max_retries=2)
    with pytest.raises(AmazonAPIError) as caught:
        client.get('/test', 'getTest')
    assert len(calls) == 3
    assert sleeps == [2.5, 2]
    assert caught.value.code == 'InternalFailure'
    assert caught.value.message == 'Server error'
    assert client.rate_limit_events == 1


def test_network_error_is_bounded_and_no_token_is_logged(caplog):
    attempts = []

    class Auth:
        def get_access_token(self):
            return 'safe-test-token'

    def reply(request):
        attempts.append(request)
        raise httpx.ConnectError('simulated failure with safe-test-token')

    client = AmazonSPAPIClient(Auth(), http=httpx.Client(transport=httpx.MockTransport(reply)),
                               sleep=lambda _: None, max_retries=1)
    with pytest.raises(AmazonAPIError) as caught:
        client.get('/test', 'getTest')
    assert len(attempts) == 2
    assert 'safe-test-token' not in str(caught.value)
    assert 'safe-test-token' not in caplog.text
