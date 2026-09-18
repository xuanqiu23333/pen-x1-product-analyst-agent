"""Catalog, Pricing and Customer Feedback API calls and normalization."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.schemas.amazon import (AmazonCatalogRecord, AmazonFeedbackRecord,
                                AmazonPricingRecord, AmazonProductSync)
from app.services.amazon_sp_api_client import AmazonSPAPIClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AmazonSPAPIProvider:
    def __init__(self, client: AmazonSPAPIClient, marketplace_id: str = 'ATVPDKIKX0DER',
                 mode: str = 'sandbox'):
        self.client = client
        self.marketplace_id = marketplace_id
        self.mode = mode

    @property
    def _status(self) -> str:
        return 'SANDBOX' if self.mode == 'sandbox' else 'LIVE'

    @staticmethod
    def _asin(asin: str) -> str:
        if not re.fullmatch(r'[A-Z0-9]{10}', asin):
            raise ValueError('ASIN 必须是 10 位大写字母或数字。')
        return asin

    def _url(self, path: str) -> str:
        return self.client.endpoint.rstrip('/') + path

    def get_catalog_item(self, asin: str) -> AmazonCatalogRecord:
        asin = self._asin(asin)
        path = f'/catalog/2022-04-01/items/{asin}'
        raw = self.client.get(path, 'getCatalogItem', {
            'marketplaceIds': self.marketplace_id,
            'includedData': 'attributes,identifiers,images,productTypes,salesRanks,summaries,relationships',
        })
        summaries = raw.get('summaries') or []
        summary = next((item for item in summaries if item.get('marketplaceId') == self.marketplace_id),
                       summaries[0] if summaries else {})
        types = raw.get('productTypes') or []
        ranks = [rank.get('rank') for group in raw.get('salesRanks') or []
                 for rank in group.get('ranks') or [] if isinstance(rank.get('rank'), int)]
        images = [image.get('link') for group in raw.get('images') or []
                  for image in group.get('images') or [] if image.get('link')]
        return AmazonCatalogRecord(
            asin=asin, title=summary.get('itemName'), brand=summary.get('brand'),
            model=summary.get('modelNumber'), product_type=types[0].get('productType') if types else None,
            images=images, sales_rank=min(ranks) if ranks else None,
            attributes=raw.get('attributes') or {}, marketplace_id=self.marketplace_id,
            source_url=self._url(path), retrieved_at=_now(),
            status=self._status if raw else 'UNKNOWN',
        )

    def get_pricing(self, asin: str) -> AmazonPricingRecord:
        asin = self._asin(asin)
        path = f'/products/pricing/v0/items/{asin}/offers'
        raw = self.client.get(path, 'getItemOffers',
                              {'MarketplaceId': self.marketplace_id, 'ItemCondition': 'New'})
        payload = raw.get('payload') or {}
        offers = payload.get('Offers') or []
        price = next((item.get('ListingPrice') for item in offers if item.get('ListingPrice')), None)
        summary = payload.get('Summary') or {}
        offer_counts = summary.get('NumberOfOffers') or []
        buy_box = next(iter(summary.get('BuyBoxPrices') or []), None)
        return AmazonPricingRecord(
            asin=asin, listing_price=price.get('Amount') if price else None,
            currency=price.get('CurrencyCode') if price else None,
            offer_count=sum(item.get('OfferCount', 0) for item in offer_counts) if offer_counts else None,
            buy_box_or_featured_offer=buy_box, marketplace_id=self.marketplace_id,
            source_url=self._url(path), retrieved_at=_now(),
            status=self._status if payload else 'UNKNOWN',
        )

    def get_customer_feedback(self, asin: str) -> list[AmazonFeedbackRecord]:
        asin = self._asin(asin)
        path = f'/customerFeedback/2024-06-01/items/{asin}/reviews/topics'
        raw = self.client.get(path, 'getItemReviewTopics',
                              {'marketplaceId': self.marketplace_id, 'sortBy': 'MENTIONS'})
        topics = raw.get('topics') or {}
        records = []
        for key, sentiment in (('positiveTopics', 'positive'), ('negativeTopics', 'negative')):
            for item in topics.get(key) or []:
                if not item.get('topic'):
                    continue
                metrics = item.get('asinMetrics') or {}
                records.append(AmazonFeedbackRecord(
                    asin=asin, topic=item['topic'], sentiment=sentiment,
                    mentions=metrics.get('numberOfMentions'),
                    star_rating_impact=metrics.get('starRatingImpact'),
                    marketplace_id=self.marketplace_id, source_url=self._url(path),
                    retrieved_at=_now(), status=self._status,
                ))
        return records

    def get_customer_feedback_trends(self, asin: str) -> dict[tuple[str, str], list[dict]]:
        asin = self._asin(asin)
        raw = self.client.get(
            f'/customerFeedback/2024-06-01/items/{asin}/reviews/trends',
            'getItemReviewTrends', {'marketplaceId': self.marketplace_id},
        )
        result = {}
        for key, sentiment in (('positiveTopics', 'positive'), ('negativeTopics', 'negative')):
            for item in (raw.get('reviewTrends') or {}).get(key) or []:
                result[(item.get('topic'), sentiment)] = [
                    {'start_date': (point.get('dateRange') or {}).get('startDate'),
                     'end_date': (point.get('dateRange') or {}).get('endDate'),
                     'occurrence_percentage': (point.get('asinMetrics') or {}).get('occurrencePercentage')}
                    for point in item.get('trendMetrics') or []
                ]
        return result

    def sync_product(self, asin: str) -> AmazonProductSync:
        catalog = self.get_catalog_item(asin)
        pricing = self.get_pricing(asin)
        feedback = self.get_customer_feedback(asin)
        trends = self.get_customer_feedback_trends(asin)
        for record in feedback:
            record.trend = trends.get((record.topic, record.sentiment), [])
        return AmazonProductSync(asin=asin, catalog=catalog, pricing=pricing,
                                 feedback=feedback, status=self._status)
