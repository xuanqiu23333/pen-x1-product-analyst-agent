import json

import httpx
import pytest

from app.services.apify_client import ApifyAPIError, ApifyClient, ApifySettings


TOKEN = 'unit-test-token-not-real'
ACTOR = 'axesso_data/amazon-reviews-scraper'


def _settings(**overrides):
    values = {
        'api_token': TOKEN,
        'actor': ACTOR,
        'base_url': 'https://api.apify.com/v2',
        'review_target_per_product': 100,
        'timeout': 10.0,
        'poll_interval_seconds': 0.01,
        'max_poll_seconds': 3.0,
    }
    values.update(overrides)
    return ApifySettings(**values)


def _client(handler, *, monotonic=None, **settings):
    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url='https://api.apify.com/v2/',
    )
    kwargs = {'sleep': lambda _: None}
    if monotonic is not None:
        kwargs['monotonic'] = monotonic
    return ApifyClient(_settings(**settings), http_client=http_client, **kwargs)


def _actor_input():
    return {'input': [{
        'asin': 'B00143JZ08', 'domainCode': 'com', 'sortBy': 'recent',
        'maxPages': 1, 'reviewerType': 'all_reviews',
        'formatType': 'current_format', 'mediaType': 'all_contents',
    }]}


def test_environment_defaults_to_free_plan_compatible_kestrel_actor(monkeypatch):
    monkeypatch.setattr('app.services.apify_client.load_dotenv', lambda: None)
    monkeypatch.delenv('APIFY_AMAZON_REVIEWS_ACTOR', raising=False)

    settings = ApifySettings.from_environment()

    assert settings.actor == 'kestrel/amazon-reviews-scraper'


def test_collect_starts_actor_waits_for_success_and_fetches_dataset_items():
    seen = []
    run_reads = 0

    def handler(request):
        nonlocal run_reads
        seen.append(request)
        assert request.headers['Authorization'] == f'Bearer {TOKEN}'
        if request.url.path == '/v2/actors/axesso_data~amazon-reviews-scraper/runs':
            assert json.loads(request.content) == _actor_input()
            return httpx.Response(201, json={'data': {'id': 'run-1', 'status': 'READY'}})
        if request.url.path == '/v2/actor-runs/run-1':
            run_reads += 1
            status = 'RUNNING' if run_reads == 1 else 'SUCCEEDED'
            return httpx.Response(200, json={'data': {
                'id': 'run-1', 'status': status,
                'defaultDatasetId': 'dataset-1' if status == 'SUCCEEDED' else None,
            }})
        if request.url.path == '/v2/datasets/dataset-1/items':
            assert request.url.params['clean'] == 'true'
            return httpx.Response(200, json=[{'reviewId': 'R1'}])
        raise AssertionError(f'unexpected path {request.url.path}')

    result = _client(handler).collect(_actor_input())

    assert result == {
        'actor_run_id': 'run-1', 'dataset_id': 'dataset-1',
        'status': 'SUCCEEDED', 'items': [{'reviewId': 'R1'}],
    }
    assert [request.method for request in seen] == ['POST', 'GET', 'GET', 'GET']


@pytest.mark.parametrize('status', ['FAILED', 'TIMED-OUT', 'ABORTED'])
def test_terminal_failure_statuses_stop_without_dataset_fetch(status):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.method == 'POST':
            return httpx.Response(201, json={'data': {'id': 'run-failed', 'status': 'READY'}})
        return httpx.Response(200, json={'data': {'id': 'run-failed', 'status': status}})

    with pytest.raises(ApifyAPIError, match=status) as captured:
        _client(handler).collect(_actor_input())

    assert captured.value.actor_run_id == 'run-failed'
    assert not any('/datasets/' in path for path in paths)


def test_polling_has_hard_timeout():
    current = -1.0

    def monotonic():
        nonlocal current
        current += 1.0
        return current

    def handler(request):
        if request.method == 'POST':
            return httpx.Response(201, json={'data': {'id': 'run-slow', 'status': 'READY'}})
        return httpx.Response(200, json={'data': {'id': 'run-slow', 'status': 'RUNNING'}})

    with pytest.raises(ApifyAPIError, match='TIMEOUT') as captured:
        _client(handler, monotonic=monotonic, max_poll_seconds=2).collect(_actor_input())

    assert captured.value.actor_run_id == 'run-slow'
    assert captured.value.retryable is True


def test_empty_dataset_is_a_valid_result():
    client = _client(lambda request: httpx.Response(200, json=[]))

    assert client.get_dataset_items('dataset-empty') == []


def test_malformed_dataset_is_rejected():
    client = _client(lambda request: httpx.Response(200, json={'items': 'bad'}))

    with pytest.raises(ApifyAPIError, match='Dataset'):
        client.get_dataset_items('dataset-bad')


def test_missing_token_is_not_configured_and_never_calls_http():
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(500)

    client = _client(handler, api_token='')

    with pytest.raises(ApifyAPIError, match='APIFY_NOT_CONFIGURED'):
        client.start_actor(_actor_input())

    assert called is False


def test_api_error_never_exposes_token():
    client = _client(lambda request: httpx.Response(
        401, json={'error': {'type': 'token-invalid', 'message': f'bad {TOKEN}'}}
    ))

    with pytest.raises(ApifyAPIError) as captured:
        client.start_actor(_actor_input())

    assert TOKEN not in str(captured.value)
    assert TOKEN not in repr(captured.value)
    assert TOKEN not in captured.value.response_excerpt
