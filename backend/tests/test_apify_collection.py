import json

from app.services.apify_client import ApifySettings
from app.services.review_collection import ReviewCollectionService
from app.services.review_store import ReviewStore


COMPETITOR = {
    'brand': 'Streamlight', 'model': 'MicroStream 66318',
    'asin': 'B00143JZ08',
    'amazon_url': 'https://www.amazon.com/dp/B00143JZ08',
    'marketplace': 'US',
}


def _row(review_id='R1'):
    return {
        'statusCode': 200, 'statusMessage': 'FOUND', 'asin': 'B00143JZ08',
        'productTitle': 'Streamlight MicroStream 66318', 'reviewId': review_id,
        'text': 'Compact and reliable.',
        'date': 'Reviewed in the United States on May 10, 2024',
        'rating': '5.0 out of 5 stars', 'title': 'Small dependable light',
        'userName': 'Private Person', 'profilePath': '/gp/profile/private',
        'author': 'Kestrel Private Person',
        'numberOfHelpful': 2, 'verified': True, 'domainCode': 'com',
    }


class FakeApifyProvider:
    provider_name = 'APIFY'
    source_type = 'APIFY_REAL'
    source_name = 'APIFY_API'

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    @property
    def status(self):
        return 'READY'

    def collect_competitors(self, competitors, max_reviews_per_product=100):
        self.calls.append((competitors, max_reviews_per_product))
        return {
            'actor_run_id': 'actor-run-1', 'dataset_id': 'dataset-1',
            'status': 'SUCCEEDED', 'reviews': self.rows,
        }


def _settings(token='unit-test-token-not-real'):
    return ApifySettings(
        api_token=token, poll_interval_seconds=0, max_poll_seconds=1,
        review_target_per_product=100,
    )


def _service(tmp_path, rows, token='unit-test-token-not-real'):
    data_root = tmp_path / 'data'
    config = data_root / 'config' / 'amazon_competitors.json'
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps([COMPETITOR]), encoding='utf-8')
    provider = FakeApifyProvider(rows)
    store = ReviewStore(data_root / 'reviews_real' / 'reviews.sqlite3')
    service = ReviewCollectionService(
        data_root, settings=_settings(token), provider=provider,
        store=store, provider_name='APIFY',
    )
    return service, provider, store


def test_missing_apify_token_returns_not_configured_without_provider_call(tmp_path):
    service, provider, _ = _service(tmp_path, [], token='')

    result = service.collect_all_competitor_reviews(10)

    assert result['status'] == 'APIFY_NOT_CONFIGURED'
    assert result['provider'] == 'APIFY'
    assert result['credential_configured'] is False
    assert provider.calls == []


def test_apify_collection_persists_run_and_writes_privacy_safe_schema_probe(tmp_path):
    service, provider, store = _service(tmp_path, [_row()])

    result = service.collect_all_competitor_reviews(10)

    assert provider.calls[0][1] == 10
    assert result['provider'] == 'APIFY'
    assert result['actor_run_id'] == 'actor-run-1'
    assert result['dataset_id'] == 'dataset-1'
    assert result['collected_reviews'] == result['valid_reviews'] == 1
    assert store.valid_reviews()[0]['source_type'] == 'APIFY_REAL'
    fixture = service.last_schema_probe
    payload = json.loads(fixture.read_text(encoding='utf-8'))
    assert fixture == service.data_root / 'fixtures' / 'apify_review_response.sample.json'
    assert len(payload) == 1
    assert 'userName' not in payload[0]
    assert 'profilePath' not in payload[0]
    assert 'author' not in payload[0]
    assert 'Private Person' not in fixture.read_text(encoding='utf-8')


def test_empty_apify_dataset_records_successful_run_without_review_rows(tmp_path):
    service, _, store = _service(tmp_path, [])

    result = service.collect_all_competitor_reviews(10)

    assert result['status'] == 'COMPLETED'
    assert result['collected_reviews'] == 0
    assert result['valid_reviews'] == 0
    assert store.valid_reviews() == []
    assert store.latest_collection('APIFY_API')['dataset_id'] == 'dataset-1'
