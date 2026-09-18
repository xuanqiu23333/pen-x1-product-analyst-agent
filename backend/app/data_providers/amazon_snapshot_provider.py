"""Merge normalized SP-API rows with official-site and fixture fallback rows."""

from app.data_providers.base import ProviderResult


class AmazonSnapshotCompetitorProvider:
    def __init__(self, fixture_provider, snapshot: dict, official_rows: list[dict]):
        self.fixture_provider = fixture_provider
        self.snapshot = snapshot
        self.official_rows = official_rows

    def get_competitor_data(self) -> ProviderResult[list[dict]]:
        fallback = self.fixture_provider.get_competitor_data()
        live = {}
        for product in self.snapshot.get('products', []):
            catalog, pricing = product.get('catalog') or {}, product.get('pricing') or {}
            if catalog.get('status') != 'LIVE' and pricing.get('status') != 'LIVE':
                continue
            key = (product.get('brand'), product.get('model'))
            live[key] = {
                'id': f"amazon-{product['asin']}", 'asin': product['asin'],
                'brand': key[0], 'model': key[1], 'product_name': catalog.get('title'),
                'price': pricing.get('listing_price'), 'currency': pricing.get('currency'),
                'battery': None, 'sales_rank': catalog.get('sales_rank'),
                'source_type': 'AMAZON_SP_API', 'data_nature': 'PUBLIC_DATA', 'status': 'LIVE',
                'source_url': (pricing.get('source_url') or catalog.get('source_url')),
                'retrieved_at': (pricing.get('retrieved_at') or catalog.get('retrieved_at')),
            }
        official = {(row.get('brand'), row.get('model')): row for row in self.official_rows}
        rows = []
        for fixture in fallback.data or []:
            key = (fixture.get('brand'), fixture.get('model'))
            row = live.get(key) or official.get(key) or fixture
            rows.append(row)
        known = {(row.get('brand'), row.get('model')) for row in rows}
        rows.extend(row for key, row in live.items() if key not in known)
        return ProviderResult(data=rows, status='LIVE' if live else 'FALLBACK',
                              source_type='MIXED' if live or official else 'FIXTURE',
                              source_name='Amazon SP-API / 品牌官网 / 演示数据')
