"""Offline transport simulation of the complete manual SP-API pipeline."""

import json

import httpx

from app.data_providers.amazon_sp_api_provider import AmazonSPAPIProvider
from app.services.amazon_auth import AmazonAuth, AmazonSettings
from app.services.amazon_sp_api_client import AmazonSPAPIClient
from app.services.amazon_sync import AmazonSyncService


def test_auth_to_snapshot_pipeline_uses_one_token_and_counts_official_operations(tmp_path):
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'amazon_competitors.json').write_text(json.dumps([
        {'brand': 'Example', 'model': 'T1', 'asin': 'B000000001', 'marketplace': 'US'}
    ]), encoding='utf-8')
    calls = []

    def reply(request):
        calls.append((request.url.path, request.headers.get('x-amz-access-token')))
        if request.url.path == '/auth/o2/token':
            return httpx.Response(200, json={'access_token': 'private-token', 'expires_in': 3600})
        assert request.headers['x-amz-access-token'] == 'private-token'
        if request.url.path.startswith('/catalog/'):
            return httpx.Response(200, json={'asin': 'B000000001', 'summaries': [
                {'marketplaceId': 'ATVPDKIKX0DER', 'itemName': 'Test Torch'}]})
        if request.url.path.startswith('/products/pricing/'):
            return httpx.Response(200, json={'payload': {'Offers': [
                {'ListingPrice': {'Amount': 23.99, 'CurrencyCode': 'USD'}}]}})
        if request.url.path.endswith('/topics'):
            return httpx.Response(200, json={'topics': {'positiveTopics': [],
                'negativeTopics': [{'topic': 'Battery', 'asinMetrics': {'numberOfMentions': 3}}]}})
        if request.url.path.endswith('/trends'):
            return httpx.Response(200, json={'reviewTrends': {'negativeTopics': []}})
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(reply))
    auth = AmazonAuth('id', 'private-secret', 'private-refresh', http=http)
    client = AmazonSPAPIClient(auth, endpoint='https://sandbox.sellingpartnerapi-na.amazon.com',
                               http=http, sleep=lambda _: None)
    provider = AmazonSPAPIProvider(client, mode='sandbox')
    settings = AmazonSettings('id', 'private-secret', 'private-refresh', mode='sandbox')
    service = AmazonSyncService(tmp_path, settings=settings, provider=provider)
    result = service.sync_all_competitors()
    assert [path for path, _ in calls].count('/auth/o2/token') == 1
    assert result.api_requests == 4
    assert (result.catalog_records, result.pricing_records, result.feedback_topics) == (1, 1, 1)
    assert result.live_records == 0
    assert result.successful_products == 1
    saved = (tmp_path / 'amazon' / 'latest' / 'snapshot.json').read_text(encoding='utf-8')
    assert 'private-token' not in saved
    assert 'private-secret' not in saved
    assert 'private-refresh' not in saved
    assert service.latest_snapshot()['evidence'][0]['data_nature'] == 'PUBLIC_FIXTURE'
