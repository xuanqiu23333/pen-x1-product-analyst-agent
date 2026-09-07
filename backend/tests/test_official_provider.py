from app.data_providers.official_site_provider import OfficialWebsiteProvider

def test_official_provider_returns_unavailable_after_network_error():
    provider = OfficialWebsiteProvider(fetcher=lambda url: (_ for _ in ()).throw(TimeoutError('timeout')))
    result = provider.get_competitor('Nitecore', 'MT2A Pro', 'https://example.invalid/product')
    assert result.status == 'UNAVAILABLE'
    assert result.data is None
    assert 'timeout' in result.fallback_reason.lower()
from app.data_providers.official_site_provider import OfficialWebsiteProvider

def test_official_provider_normalizes_public_page_fields():
    html='<html><head><title>Nitecore MT2A Pro</title></head><body>Price $39.95</body></html>'
    result=OfficialWebsiteProvider(fetcher=lambda _: html).get_competitor('Nitecore','MT2A Pro','https://example.com/product')
    assert result.status == 'LIVE'
    assert result.data['product_name'] == 'Nitecore MT2A Pro'
    assert result.data['price'] == '$39.95'
