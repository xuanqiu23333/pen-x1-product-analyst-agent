from __future__ import annotations
from collections.abc import Callable
from bs4 import BeautifulSoup
import httpx
from app.data_providers.base import ProviderResult

class AmazonProductProvider:
    """Best-effort public product summary provider. It never fetches review pages."""
    def __init__(self, fetcher: Callable[[str], str] | None = None, timeout_seconds: float = 12.0):
        self.fetcher = fetcher or self._fetch
        self.timeout_seconds = timeout_seconds
    def _fetch(self, url: str) -> str:
        response = httpx.get(url, timeout=self.timeout_seconds, follow_redirects=True, headers={'User-Agent':'PEN-X1-Demo/1.0 (+public-product-research)'})
        response.raise_for_status(); return response.text
    def get_product(self, asin: str, url: str) -> ProviderResult[dict]:
        try:
            soup = BeautifulSoup(self.fetcher(url), 'html.parser')
            title = soup.select_one('#productTitle')
            price = soup.select_one('.a-price .a-offscreen')
            rating = soup.select_one('#acrPopover')
            count = soup.select_one('#acrCustomerReviewText')
            bullets = [item.get_text(' ', strip=True) for item in soup.select('#feature-bullets li') if item.get_text(' ', strip=True)]
            return ProviderResult(data={'asin':asin, 'title':title.get_text(' ', strip=True) if title else None, 'price':price.get_text(' ', strip=True) if price else None, 'rating':rating.get('title') if rating else None, 'review_count':count.get_text(' ', strip=True) if count else None, 'bullet_points':bullets, 'url':url}, status='LIVE', source_type='AMAZON_PRODUCT', source_name='Amazon public product page', source_url=url)
        except Exception as error:
            return ProviderResult(data=None, status='UNAVAILABLE', source_type='AMAZON_PRODUCT', source_name='Amazon public product page', source_url=url, fallback_reason=str(error), warnings=['Amazon product source unavailable; fixture fallback required.'])
