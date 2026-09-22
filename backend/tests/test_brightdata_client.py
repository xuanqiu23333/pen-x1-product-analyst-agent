import json

import httpx
import pytest

from app.services.brightdata_client import (
    BrightDataAPIError,
    BrightDataClient,
    BrightDataSettings,
)


TOKEN = 'unit-test-token-not-real'
DATASET_ID = 'gd_le8e811kzy4ggddlq'


def _settings(**overrides):
    values = {
        'api_token': TOKEN,
        'dataset_id': DATASET_ID,
        'review_target_per_product': 100,
        'timeout': 10.0,
        'poll_interval_seconds': 0.01,
        'max_poll_seconds': 3.0,
        'max_retries': 2,
        'schema_confirmed': False,
    }
    values.update(overrides)
    return BrightDataSettings(**values)


def _client(handler, **settings):
    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url='https://api.brightdata.com',
    )
    return BrightDataClient(
        _settings(**settings), http_client=http_client, sleep=lambda _: None
    )


def test_collect_uses_web_scraper_v3_trigger_progress_and_snapshot():
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers['Authorization'] == f'Bearer {TOKEN}'
        if request.url.path == '/datasets/v3/trigger':
            assert request.url.params['dataset_id'] == DATASET_ID
            assert request.url.params['format'] == 'json'
            assert request.url.params['uncompressed_webhook'] == 'true'
            assert json.loads(request.content) == [{'url': 'https://www.amazon.com/dp/B000000001'}]
            return httpx.Response(200, json={'snapshot_id': 's_test'})
        if request.url.path == '/datasets/v3/progress/s_test':
            return httpx.Response(200, json={'snapshot_id': 's_test', 'status': 'ready'})
        if request.url.path == '/datasets/v3/snapshot/s_test':
            assert request.url.params['format'] == 'json'
            return httpx.Response(200, json=[{'review_id': 'R1'}])
        raise AssertionError(f'unexpected path {request.url.path}')

    snapshot_id, rows = _client(handler).collect([
        {'url': 'https://www.amazon.com/dp/B000000001'}
    ])

    assert snapshot_id == 's_test'
    assert rows == [{'review_id': 'R1'}]
    assert [request.url.path for request in seen] == [
        '/datasets/v3/trigger',
        '/datasets/v3/progress/s_test',
        '/datasets/v3/snapshot/s_test',
    ]


@pytest.mark.parametrize('wrapper', ['data', 'results'])
def test_download_accepts_documented_list_wrappers(wrapper):
    def handler(request):
        return httpx.Response(200, json={wrapper: [{'review_id': 'R1'}]})

    assert _client(handler).download_snapshot('s_test') == [{'review_id': 'R1'}]


def test_download_rejects_malformed_shape():
    client = _client(lambda request: httpx.Response(200, json={'status': 'ready'}))

    with pytest.raises(BrightDataAPIError, match='快照数据格式无效') as captured:
        client.download_snapshot('s_test')

    assert captured.value.retryable is False
    assert captured.value.snapshot_id == 's_test'


@pytest.mark.parametrize('status_code', [401, 403])
def test_authentication_errors_are_not_retried_or_leaked(status_code):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code, json={'error': f'bad token {TOKEN}'})

    with pytest.raises(BrightDataAPIError) as captured:
        _client(handler).trigger_collection([{'url': 'https://www.amazon.com/dp/B000000001'}])

    assert attempts == 1
    assert captured.value.retryable is False
    assert TOKEN not in str(captured.value)
    assert TOKEN not in repr(captured.value)


def test_json_error_exposes_sanitized_diagnostics_without_secrets():
    long_detail = 'x' * 2500

    def handler(request):
        return httpx.Response(400, json={
            'code': 'validation_error',
            'message': f'Bad payload; Authorization: Bearer {TOKEN}',
            'api_token': TOKEN,
            'user': 'person@example.com',
            'ip': '192.0.2.1',
            'detail': long_detail,
        })

    with pytest.raises(BrightDataAPIError) as captured:
        _client(handler).trigger_collection([{'url': 'https://example.com'}])

    error = captured.value
    assert error.status_code == 400
    assert error.error_code == 'validation_error'
    assert error.error_message == 'Bad payload; Authorization: [REDACTED]'
    assert len(error.response_excerpt) <= 2000
    assert TOKEN not in error.response_excerpt
    assert '"api_token": "[REDACTED]"' in error.response_excerpt
    assert 'person@example.com' not in error.response_excerpt
    assert '192.0.2.1' not in error.response_excerpt
    assert TOKEN not in str(error)
    assert TOKEN not in repr(error)


def test_text_error_body_is_preserved_and_sensitive_labels_are_redacted():
    body = f'API Token={TOKEN}; authorization=Bearer another-secret; invalid input'
    client = _client(lambda request: httpx.Response(400, text=body))

    with pytest.raises(BrightDataAPIError) as captured:
        client.trigger_collection([{'url': 'https://example.com'}])

    error = captured.value
    assert error.error_code is None
    assert error.error_message == 'Bright Data API 请求失败（HTTP 400）'
    assert error.response_excerpt == (
        'API Token=[REDACTED]; authorization=[REDACTED]; invalid input'
    )
    assert TOKEN not in repr(error)


@pytest.mark.parametrize('status_code', [429, 500, 503])
def test_retryable_errors_stop_after_configured_retries(status_code):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code, json={'error': 'temporary'})

    with pytest.raises(BrightDataAPIError) as captured:
        _client(handler, max_retries=2).trigger_collection([{'url': 'https://example.com'}])

    assert attempts == 3
    assert captured.value.retryable is True


def test_retryable_request_can_recover():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, json={'error': 'temporary'})
        return httpx.Response(200, json={'snapshot_id': 's_ok'})

    assert _client(handler, max_retries=2).trigger_collection([{'url': 'https://example.com'}]) == 's_ok'
    assert attempts == 3


def test_trigger_requires_snapshot_id():
    client = _client(lambda request: httpx.Response(200, json={'status': 'started'}))

    with pytest.raises(BrightDataAPIError, match='未返回 snapshot_id') as captured:
        client.trigger_collection([{'url': 'https://example.com'}])

    assert captured.value.retryable is False


@pytest.mark.parametrize('snapshot_status', ['failed', 'canceled'])
def test_failed_or_canceled_snapshot_stops_without_download(snapshot_status):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith('/trigger'):
            return httpx.Response(200, json={'snapshot_id': 's_failed'})
        return httpx.Response(200, json={'status': snapshot_status, 'error_message': 'collection stopped'})

    with pytest.raises(BrightDataAPIError, match='collection stopped') as captured:
        _client(handler).collect([{'url': 'https://example.com'}])

    assert captured.value.snapshot_id == 's_failed'
    assert not any('/snapshot/' in path for path in paths)


def test_polling_has_hard_timeout():
    current = -1.0

    def monotonic():
        nonlocal current
        current += 1.0
        return current

    def handler(request):
        if request.url.path.endswith('/trigger'):
            return httpx.Response(200, json={'snapshot_id': 's_slow'})
        return httpx.Response(200, json={'status': 'running'})

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url='https://api.brightdata.com'
    )
    client = BrightDataClient(
        _settings(max_poll_seconds=2), http_client=http_client,
        sleep=lambda _: None, monotonic=monotonic,
    )

    with pytest.raises(BrightDataAPIError, match='TIMEOUT') as captured:
        client.collect([{'url': 'https://example.com'}])

    assert captured.value.retryable is True
    assert captured.value.snapshot_id == 's_slow'
