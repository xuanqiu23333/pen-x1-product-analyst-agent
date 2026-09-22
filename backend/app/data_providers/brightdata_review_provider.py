"""Bright Data provider: Amazon product URLs in, raw structured reviews out."""

from app.services.brightdata_client import BrightDataClient


class BrightDataReviewProvider:
    provider_name = 'BRIGHTDATA'
    source_type = 'BRIGHTDATA_REAL'
    source_name = 'BRIGHTDATA_API'

    def __init__(self, client: BrightDataClient):
        self.client = client

    @property
    def status(self) -> str:
        return 'READY' if self.client.settings.configured else 'NOT_CONFIGURED'

    @staticmethod
    def _input(product_url: str, max_reviews: int) -> dict:
        return {
            'url': product_url,
            'max_reviews': max_reviews,
            'variation_specific': False,
            'reviews_to_not_include': [],
        }

    def collect_product_reviews(self, product_url: str, asin: str,
                                product_name: str, max_reviews: int = 100) -> list[dict]:
        _, rows = self.client.collect([self._input(product_url, max_reviews)])
        return rows

    def collect_competitors(self, competitors: list[dict],
                            max_reviews_per_product: int = 100) -> dict:
        inputs = [self._input(item['amazon_url'], max_reviews_per_product)
                  for item in competitors]
        snapshot_id, rows = self.client.collect(inputs)
        return {'snapshot_id': snapshot_id, 'reviews': rows}
