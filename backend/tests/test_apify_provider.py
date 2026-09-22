from app.data_providers.apify_review_provider import ApifyReviewProvider
from app.data_providers.review_collection_provider import ReviewCollectionProvider


class FakeSettings:
    configured = True

    def __init__(self, actor='axesso_data/amazon-reviews-scraper'):
        self.actor = actor


class FakeClient:
    def __init__(self, actor='axesso_data/amazon-reviews-scraper', items=None):
        self.settings = FakeSettings(actor)
        self.actor_input = None
        self.items = items or [{'reviewId': 'R1'}]

    def collect(self, actor_input):
        self.actor_input = actor_input
        return {
            'actor_run_id': 'run-1', 'dataset_id': 'dataset-1',
            'status': 'SUCCEEDED', 'items': self.items,
        }


def _competitor():
    return {
        'brand': 'Streamlight', 'model': 'MicroStream 66318',
        'asin': 'B00143JZ08',
        'amazon_url': 'https://www.amazon.com/dp/B00143JZ08',
        'marketplace': 'US',
    }


def test_provider_implements_shared_contract_and_official_minimal_input():
    client = FakeClient()
    provider = ApifyReviewProvider(client)

    result = provider.collect_competitors([_competitor()], 10)

    assert isinstance(provider, ReviewCollectionProvider)
    assert provider.provider_name == 'APIFY'
    assert provider.status == 'READY'
    assert client.actor_input == {'input': [{
        'asin': 'B00143JZ08', 'domainCode': 'com', 'sortBy': 'recent',
        'maxPages': 1, 'reviewerType': 'all_reviews',
        'formatType': 'current_format', 'mediaType': 'all_contents',
    }]}
    assert result == {
        'actor_run_id': 'run-1', 'dataset_id': 'dataset-1',
        'status': 'SUCCEEDED', 'reviews': [{'reviewId': 'R1'}],
        'raw_record_count': 1,
    }


def test_kestrel_input_caps_free_smoke_and_discards_status_rows():
    client = FakeClient('kestrel/amazon-reviews-scraper', items=[
        {'type': 'status', 'asin': 'B00143JZ08', 'status': 'ok'},
        {'type': 'review', 'review_id': 'R1', 'asin': 'B00143JZ08'},
    ])
    provider = ApifyReviewProvider(client)

    result = provider.collect_competitors([_competitor()], 15)

    assert client.actor_input == {
        'asins': ['B00143JZ08'],
        'domain': 'com',
        'maxReviewsPerProduct': 13,
        'includeProductRow': False,
    }
    assert result['raw_record_count'] == 2
    assert result['reviews'] == [
        {'type': 'review', 'review_id': 'R1', 'asin': 'B00143JZ08'}
    ]


def test_collect_product_reviews_returns_only_raw_items():
    client = FakeClient()
    provider = ApifyReviewProvider(client)

    rows = provider.collect_product_reviews(
        _competitor()['amazon_url'], 'B00143JZ08', 'Streamlight MicroStream 66318', 10
    )

    assert rows == [{'reviewId': 'R1'}]
