from app.data_providers.amazon_sp_api_provider import AmazonSPAPIProvider


class StubClient:
    endpoint = 'https://sandbox.sellingpartnerapi-na.amazon.com'

    def __init__(self):
        self.calls = []

    def get(self, path, operation, params=None):
        self.calls.append((path, operation, params))
        if operation == 'getCatalogItem':
            return {'asin': 'B000000001', 'summaries': [{'marketplaceId': 'ATVPDKIKX0DER',
                    'itemName': 'Test Torch', 'brand': 'Example', 'modelNumber': 'T1'}],
                    'productTypes': [{'productType': 'FLASHLIGHT'}],
                    'salesRanks': [{'ranks': [{'rank': 48, 'title': 'Lights'}]}],
                    'images': [{'images': [{'link': 'https://example.com/a.jpg'}]}],
                    'attributes': {'color': [{'value': 'black'}]}}
        if operation == 'getItemOffers':
            return {'payload': {'Summary': {'NumberOfOffers': [{'OfferCount': 2}],
                    'BuyBoxPrices': [{'LandedPrice': {'Amount': 24.99, 'CurrencyCode': 'USD'}}]},
                    'Offers': [{'ListingPrice': {'Amount': 23.99, 'CurrencyCode': 'USD'}}]}}
        if operation == 'getItemReviewTopics':
            return {'topics': {'positiveTopics': [{'topic': 'Brightness', 'asinMetrics': {
                'numberOfMentions': 7, 'starRatingImpact': 0.4}}],
                'negativeTopics': [{'topic': 'Battery', 'asinMetrics': {
                    'numberOfMentions': 3, 'starRatingImpact': -0.7}}]}}
        return {'reviewTrends': {'negativeTopics': [{'topic': 'Battery', 'trendMetrics': [
            {'dateRange': {'startDate': '2026-01-01'}, 'asinMetrics': {'occurrencePercentage': 12.5}}]}]}}


def test_provider_uses_four_official_operations_and_normalizes_observed_fields():
    client = StubClient()
    provider = AmazonSPAPIProvider(client, marketplace_id='ATVPDKIKX0DER', mode='sandbox')
    product = provider.sync_product('B000000001')
    assert product.catalog.title == 'Test Torch'
    assert product.catalog.sales_rank == 48
    assert product.catalog.status == 'SANDBOX'
    assert product.pricing.listing_price == 23.99
    assert product.pricing.offer_count == 2
    assert product.pricing.buy_box_or_featured_offer['LandedPrice']['Amount'] == 24.99
    assert [(item.topic, item.sentiment, item.mentions) for item in product.feedback] == [
        ('Brightness', 'positive', 7), ('Battery', 'negative', 3)]
    assert product.feedback[1].trend[0]['occurrence_percentage'] == 12.5
    assert client.calls[0] == ('/catalog/2022-04-01/items/B000000001', 'getCatalogItem', {
        'marketplaceIds': 'ATVPDKIKX0DER', 'includedData': 'attributes,identifiers,images,productTypes,salesRanks,summaries,relationships'})
    assert client.calls[1][2] == {'MarketplaceId': 'ATVPDKIKX0DER', 'ItemCondition': 'New'}
    assert client.calls[2][2] == {'marketplaceId': 'ATVPDKIKX0DER', 'sortBy': 'MENTIONS'}
    assert client.calls[3][2] == {'marketplaceId': 'ATVPDKIKX0DER'}


def test_absent_api_fields_remain_unknown_instead_of_inventing_prices_or_topics():
    class EmptyClient(StubClient):
        def get(self, path, operation, params=None):
            return {} if operation != 'getCatalogItem' else {'asin': 'B000000001'}

    product = AmazonSPAPIProvider(EmptyClient(), mode='production').sync_product('B000000001')
    assert product.catalog.title is None
    assert product.catalog.brand is None
    assert product.pricing.listing_price is None
    assert product.pricing.buy_box_or_featured_offer is None
    assert product.feedback == []
