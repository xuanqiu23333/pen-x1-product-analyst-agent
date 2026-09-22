from app.data_providers.brightdata_review_provider import BrightDataReviewProvider
from app.data_providers.review_collection_provider import ReviewCollectionProvider


def _competitors(count=4):
    return [
        {
            'brand': f'Brand{index}', 'model': f'Model{index}',
            'asin': f'B00000000{index}',
            'amazon_url': f'https://www.amazon.com/dp/B00000000{index}',
            'marketplace': 'US',
        }
        for index in range(1, count + 1)
    ]


class FakeClient:
    def __init__(self):
        self.inputs = None
        self.settings = type('Settings', (), {'configured': True})()

    def collect(self, inputs):
        self.inputs = inputs
        return 's_batch', [{'review_id': 'R1', 'url': inputs[0]['url']}]


def test_collect_competitors_submits_one_batch_with_requested_limit():
    client = FakeClient()
    provider = BrightDataReviewProvider(client)

    assert isinstance(provider, ReviewCollectionProvider)
    assert provider.provider_name == 'BRIGHTDATA'
    assert provider.status == 'READY'

    result = provider.collect_competitors(_competitors(), 100)

    assert result['snapshot_id'] == 's_batch'
    assert result['reviews'] == [{'review_id': 'R1', 'url': client.inputs[0]['url']}]
    assert len(client.inputs) == 4
    assert all(item['max_reviews'] == 100 for item in client.inputs)
    assert all(item['variation_specific'] is False for item in client.inputs)
    assert all(item['reviews_to_not_include'] == [] for item in client.inputs)


def test_collect_product_reviews_uses_single_input_and_returns_only_rows():
    client = FakeClient()
    provider = BrightDataReviewProvider(client)

    rows = provider.collect_product_reviews(
        'https://www.amazon.com/dp/B000000001', 'B000000001', 'Product One', 5
    )

    assert rows == [{'review_id': 'R1', 'url': client.inputs[0]['url']}]
    assert client.inputs == [{
        'url': 'https://www.amazon.com/dp/B000000001',
        'max_reviews': 5,
        'variation_specific': False,
        'reviews_to_not_include': [],
    }]
