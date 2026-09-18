import json

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import get_amazon_service
from app.schemas.amazon import AmazonCatalogRecord, AmazonFeedbackRecord, AmazonPricingRecord
from app.services.amazon_auth import AmazonSettings
from app.services.amazon_sync import AmazonSyncService


def _config(root, asin='B000000001'):
    folder = root / 'config'
    folder.mkdir()
    (folder / 'amazon_competitors.json').write_text(json.dumps([
        {'brand': 'Example', 'model': 'T1', 'asin': asin, 'marketplace': 'US'},
        {'brand': 'Missing', 'model': 'T2', 'asin': '', 'marketplace': 'US'},
    ]), encoding='utf-8')


def test_missing_credentials_keeps_manual_sync_available_without_network(tmp_path):
    _config(tmp_path)
    summary = AmazonSyncService(tmp_path, settings=AmazonSettings()).sync_all_competitors()
    assert summary.status == 'NOT_CONFIGURED'
    assert summary.target_products == 2
    assert summary.api_requests == 0
    assert summary.successful_products == 0
    assert summary.fallback_records == 2
    assert (tmp_path / 'amazon' / 'latest' / 'snapshot.json').exists()


def test_sync_counts_normalized_records_and_persists_fact_evidence_without_secrets(tmp_path):
    _config(tmp_path)

    class Client:
        api_requests = 4
        api_errors = 0
        rate_limit_events = 0
        rate_limits = {'getCatalogItem': '1'}
        request_ids = ['safe-request-id']

    class Provider:
        client = Client()

        def get_catalog_item(self, asin):
            return AmazonCatalogRecord(asin=asin, title='Test Torch', brand='Example',
                model='T1', sales_rank=48, marketplace_id='ATVPDKIKX0DER',
                source_url='https://sellingpartnerapi-na.amazon.com/catalog/item',
                retrieved_at='2026-09-18T00:00:00Z', status='LIVE')

        def get_pricing(self, asin):
            return AmazonPricingRecord(asin=asin, listing_price=23.99, currency='USD',
                marketplace_id='ATVPDKIKX0DER', source_url='https://sellingpartnerapi-na.amazon.com/pricing',
                retrieved_at='2026-09-18T00:00:00Z', status='LIVE')

        def get_customer_feedback(self, asin):
            return [AmazonFeedbackRecord(asin=asin, topic='Battery', sentiment='negative',
                mentions=3, marketplace_id='ATVPDKIKX0DER',
                source_url='https://sellingpartnerapi-na.amazon.com/feedback',
                retrieved_at='2026-09-18T00:00:00Z', status='LIVE')]

        def get_customer_feedback_trends(self, asin):
            return {('Battery', 'negative'): []}

    settings = AmazonSettings('id', 'secret-must-not-save', 'refresh-must-not-save',
                              mode='production', real_data_enabled=True)
    service = AmazonSyncService(tmp_path, settings=settings, provider=Provider())
    summary = service.sync_all_competitors()
    snapshot = service.latest_snapshot()
    assert summary.status == 'PARTIAL'
    assert (summary.target_products, summary.successful_products, summary.failed_products) == (2, 1, 1)
    assert (summary.catalog_records, summary.pricing_records, summary.feedback_topics) == (1, 1, 1)
    assert summary.api_requests == 4
    assert summary.live_records == 3
    assert len(snapshot['facts']) >= 3
    assert snapshot['evidence'][0]['source_type'] == 'AMAZON_CUSTOMER_FEEDBACK'
    assert 'secret-must-not-save' not in json.dumps(snapshot)
    assert 'refresh-must-not-save' not in json.dumps(snapshot)
    assert len(list((tmp_path / 'amazon' / 'history').rglob('*.json'))) == 1
    app.dependency_overrides[get_amazon_service] = lambda: service
    try:
        client = TestClient(app)
        assert client.get('/api/amazon/sync/latest').json()['summary']['feedback_topics'] == 1
        assert client.get('/api/amazon/products/B000000001').json()['catalog']['title'] == 'Test Torch'
        assert len(client.get('/api/amazon/products/B000000001/feedback').json()) == 1
        assert client.get('/api/amazon/products').json()[0]['asin'] == 'B000000001'
    finally:
        app.dependency_overrides.clear()


def test_empty_api_payload_is_not_counted_as_successful_live_product(tmp_path):
    _config(tmp_path)

    class EmptyProvider:
        def get_catalog_item(self, asin):
            return AmazonCatalogRecord(asin=asin, marketplace_id='ATVPDKIKX0DER',
                source_url='https://sellingpartnerapi-na.amazon.com/catalog/item',
                retrieved_at='2026-09-18T00:00:00Z', status='UNKNOWN')

        def get_pricing(self, asin):
            return AmazonPricingRecord(asin=asin, marketplace_id='ATVPDKIKX0DER',
                source_url='https://sellingpartnerapi-na.amazon.com/pricing',
                retrieved_at='2026-09-18T00:00:00Z', status='UNKNOWN')

        def get_customer_feedback(self, asin):
            return []

        def get_customer_feedback_trends(self, asin):
            return {}

    settings = AmazonSettings('id', 'secret', 'refresh', mode='production', real_data_enabled=True)
    summary = AmazonSyncService(tmp_path, settings, EmptyProvider()).sync_all_competitors()
    assert summary.successful_products == 0
    assert summary.live_records == 0
