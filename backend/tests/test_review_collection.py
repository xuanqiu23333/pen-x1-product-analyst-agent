import json

import pytest

from app.services.brightdata_client import BrightDataSettings
from app.services.review_collection import ReviewCollectionService
from app.services.review_store import ReviewStore


def _competitor(index, with_url=True):
    return {
        'brand': f'Brand{index}', 'model': f'Model{index}',
        'asin': f'B00000000{index}',
        'amazon_url': f'https://www.amazon.com/dp/B00000000{index}' if with_url else '',
        'marketplace': 'US',
    }


def _review(competitor, review_id='R1', valid=True):
    return {
        'review_id': review_id,
        'asin': competitor['asin'],
        'product_url': competitor['amazon_url'],
        'review_rating': 4 if valid else 9,
        'review_title': 'Useful',
        'review_text': 'Bright and compact',
        'review_date': '2025-03-10',
        'verified_purchase': True,
        'helpful_votes': 2,
        'review_url': f'https://www.amazon.com/review/{review_id}',
        'author': 'Private Person',
    }


class FakeProvider:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.calls = []

    def collect_competitors(self, competitors, max_reviews_per_product=100):
        self.calls.append((competitors, max_reviews_per_product))
        if self.error:
            raise self.error
        return {'snapshot_id': 's_test', 'reviews': self.rows}


def _write_config(data_root, competitors):
    path = data_root / 'config' / 'amazon_competitors.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(competitors), encoding='utf-8')


def _service(tmp_path, competitors, *, token='token-for-unit-test', schema_confirmed=False,
             rows=None, target=100):
    data_root = tmp_path / 'data'
    _write_config(data_root, competitors)
    provider = FakeProvider(rows)
    settings = BrightDataSettings(
        api_token=token, review_target_per_product=target,
        poll_interval_seconds=0, max_poll_seconds=1,
        schema_confirmed=schema_confirmed,
    )
    store = ReviewStore(data_root / 'reviews_real' / 'reviews.sqlite3')
    return ReviewCollectionService(data_root, settings=settings, provider=provider, store=store), provider, store


def test_missing_token_returns_not_configured_without_calling_provider(tmp_path):
    competitors = [_competitor(index) for index in range(1, 5)]
    service, provider, _ = _service(tmp_path, competitors, token='')

    result = service.collect_all_competitor_reviews()

    assert result['status'] == 'NOT_CONFIGURED'
    assert result['credential_configured'] is False
    assert result['requested_reviews'] == 0
    assert provider.calls == []


def test_missing_product_urls_returns_required_without_calling_provider(tmp_path):
    competitors = [_competitor(index, with_url=False) for index in range(1, 5)]
    service, provider, _ = _service(tmp_path, competitors)

    result = service.collect_all_competitor_reviews(5)

    assert result['status'] == 'PRODUCT_URL_REQUIRED'
    assert all(item['status'] == 'PRODUCT_URL_REQUIRED' for item in result['products'])
    assert provider.calls == []


@pytest.mark.parametrize('target,configured_count', [(6, 1), (5, 2)])
def test_unconfirmed_schema_blocks_large_or_multi_product_collection(
        tmp_path, target, configured_count):
    competitors = [
        _competitor(index, with_url=index <= configured_count) for index in range(1, 5)
    ]
    service, provider, _ = _service(tmp_path, competitors, schema_confirmed=False)

    result = service.collect_all_competitor_reviews(target)

    assert result['status'] == 'SCHEMA_CONFIRMATION_REQUIRED'
    assert result['requested_reviews'] == 0
    assert provider.calls == []


@pytest.mark.parametrize('target', [0, 301])
def test_collection_rejects_unsafe_target(tmp_path, target):
    service, _, _ = _service(tmp_path, [_competitor(1)])

    with pytest.raises(ValueError, match='1 到 300'):
        service.collect_all_competitor_reviews(target)


def test_one_product_five_review_probe_is_privacy_safe_and_writes_sqlite(tmp_path):
    competitor = _competitor(1)
    rows = [_review(competitor, f'R{index}') for index in range(1, 6)]
    competitors = [competitor] + [_competitor(index, False) for index in range(2, 5)]
    service, provider, store = _service(tmp_path, competitors, rows=rows)

    result = service.collect_all_competitor_reviews(5)

    assert result['status'] == 'PARTIAL'
    assert result['requested_reviews'] == 5
    assert result['collected_reviews'] == 5
    assert result['valid_reviews'] == 5
    assert store.stats()['sources']['BRIGHTDATA_REAL'] == 5
    assert provider.calls[0][1] == 5
    assert service.latest_collection()['target_reviews'] == result['target_reviews'] == 20
    probe_path = service.last_schema_probe
    probe = json.loads(probe_path.read_text(encoding='utf-8'))
    assert probe['record_count'] == 5
    assert probe['fields']['author'] == ['str']
    serialized = probe_path.read_text(encoding='utf-8')
    assert 'Private Person' not in serialized
    assert 'author' not in probe['safe_previews'][0]
    assert 'review_text' not in probe['safe_previews'][0]
    assert 'title' not in probe['safe_previews'][0]


def test_malformed_review_is_counted_invalid_without_fabrication(tmp_path):
    competitor = _competitor(1)
    malformed = _review(competitor, 'BAD', valid=False)
    service, _, store = _service(
        tmp_path, [competitor], rows=[malformed], schema_confirmed=True
    )

    result = service.collect_all_competitor_reviews(1)

    assert result['collected_reviews'] == 1
    assert result['valid_reviews'] == 0
    assert result['invalid_reviews'] == 1
    assert store.valid_reviews() == []


def test_four_products_request_four_hundred_and_report_actual_rows(tmp_path):
    competitors = [_competitor(index) for index in range(1, 5)]
    rows = [_review(item, f'R{index}') for index, item in enumerate(competitors, start=1)]
    service, provider, store = _service(
        tmp_path, competitors, rows=rows, schema_confirmed=True
    )

    result = service.collect_all_competitor_reviews(100)

    assert result['status'] == 'COMPLETED'
    assert result['target_products'] == 4
    assert result['requested_reviews'] == 400
    assert result['collected_reviews'] == 4
    assert result['valid_reviews'] == 4
    assert len(provider.calls[0][0]) == 4
    assert [item['valid_reviews'] for item in result['products']] == [1, 1, 1, 1]
    assert store.latest_collection()['requested_reviews'] == 400


def test_latest_without_run_reports_current_configuration_without_network(tmp_path):
    competitors = [_competitor(1)] + [_competitor(index, False) for index in range(2, 5)]
    service, provider, _ = _service(tmp_path, competitors)

    latest = service.latest_collection()

    assert latest['status'] == 'SCHEMA_CONFIRMATION_REQUIRED'
    assert latest['collected_reviews'] == 0
    assert latest['target_reviews'] == 400
    assert provider.calls == []
