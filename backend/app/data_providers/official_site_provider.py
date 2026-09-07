from __future__ import annotations
from collections.abc import Callable
from bs4 import BeautifulSoup
import httpx
from app.data_providers.base import ProviderResult

class OfficialWebsiteProvider:
    """Best-effort public product-page reader; never bypasses access controls."""
    def __init__(self, fetcher: Callable[[str], str] | None = None, timeout_seconds: float = 12.0):
        self.fetcher = fetcher or self._fetch
        self.timeout_seconds = timeout_seconds

    def _fetch(self, url: str) -> str:
        response = httpx.get(url, timeout=self.timeout_seconds, follow_redirects=True, headers={'User-Agent':'PEN-X1-Demo/1.0 (+public-product-research)'})
        response.raise_for_status()
        return response.text

    def get_competitor(self, brand: str, model: str, url: str) -> ProviderResult[dict]:
        try:
            html = self.fetcher(url)
            soup = BeautifulSoup(html, 'html.parser')
            title = (soup.find('meta', property='og:title') or soup.find('title'))
            title_text = title.get('content') if title and title.has_attr('content') else (title.get_text(' ', strip=True) if title else f'{brand} {model}')
            text = soup.get_text(' ', strip=True)
            return ProviderResult(data={'id':f'official-{brand.lower()}-{model.lower().replace(" ", "-")}', 'brand':brand, 'model':model, 'product_name':title_text, 'price':self._find_currency(text), 'battery':None, 'max_lumen':None, 'runtime':None, 'weight':None, 'dimensions':None, 'ip_rating':None, 'charging':None, 'features':[], 'source_url':url, 'source_type':'OFFICIAL_SITE', 'data_nature':'PUBLIC_DATA', 'status':'LIVE'}, status='LIVE', source_type='OFFICIAL_SITE', source_name=f'{brand} official website', source_url=url)
        except Exception as error:
            return ProviderResult(data=None, status='UNAVAILABLE', source_type='OFFICIAL_SITE', source_name=f'{brand} official website', source_url=url, fallback_reason=str(error), warnings=['Official source unavailable; fixture fallback required.'])

    @staticmethod
    def _find_currency(text: str) -> str | None:
        import re
        match = re.search(r'\$\s?\d+(?:\.\d{2})?', text)
        return match.group(0) if match else None
