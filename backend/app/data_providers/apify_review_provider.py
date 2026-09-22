"""Apify Amazon Reviews Actor provider: configured ASINs in, raw items out."""

from app.services.apify_client import ApifyClient


class ApifyReviewProvider:
    provider_name = 'APIFY'
    source_type = 'APIFY_REAL'
    source_name = 'APIFY_API'

    def __init__(self, client: ApifyClient):
        self.client = client

    @property
    def status(self) -> str:
        return 'READY' if self.client.settings.configured else 'APIFY_NOT_CONFIGURED'

    def _is_kestrel(self) -> bool:
        return self.client.settings.actor == 'kestrel/amazon-reviews-scraper'

    def _input(self, competitors: list[dict], max_reviews_per_product: int) -> dict:
        if self._is_kestrel():
            return {
                'asins': [item['asin'] for item in competitors],
                'domain': 'com',
                'maxReviewsPerProduct': min(max_reviews_per_product, 13),
                'includeProductRow': False,
            }
        return {'input': [{
            'asin': item['asin'],
            'domainCode': 'com',
            'sortBy': 'recent',
            'maxPages': 1,
            'reviewerType': 'all_reviews',
            'formatType': 'current_format',
            'mediaType': 'all_contents',
        } for item in competitors]}

    def collect_product_reviews(self, product_url: str, asin: str,
                                product_name: str, max_reviews: int = 100) -> list[dict]:
        result = self.client.collect(self._input([{'asin': asin}], max_reviews))
        items = result['items']
        return ([item for item in items if item.get('type') == 'review']
                if self._is_kestrel() else items)

    def collect_competitors(self, competitors: list[dict],
                            max_reviews_per_product: int = 100) -> dict:
        result = self.client.collect(self._input(competitors, max_reviews_per_product))
        items = result['items']
        reviews = ([item for item in items if item.get('type') == 'review']
                   if self._is_kestrel() else items)
        return {
            'actor_run_id': result['actor_run_id'],
            'dataset_id': result['dataset_id'],
            'status': result['status'],
            'reviews': reviews,
            'raw_record_count': len(items),
        }
