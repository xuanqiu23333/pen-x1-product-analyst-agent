import httpx
import pytest

from app.services.amazon_auth import AmazonSettings
from app.services.amazon_sp_api_client import AmazonSPAPIClient


def test_official_us_sandbox_order_is_normalized_without_copying_personal_data():
    from app.services.amazon_orders import AmazonOrdersSandbox
    seen = []

    class Auth:
        def get_access_token(self):
            return 'safe-test-token'

    def reply(request):
        seen.append(request)
        return httpx.Response(200, json={'order': {
            'orderId': '114-9876543-1234567', 'createdTime': '2025-03-10T14:00:00Z',
            'lastUpdatedTime': '2025-03-10T14:30:00Z',
            'fulfillment': {'fulfillmentStatus': 'UNSHIPPED', 'fulfilledBy': 'MERCHANT'},
            'salesChannel': {'channelName': 'AMAZON', 'marketplaceId': 'ATVPDKIKX0DER'},
            'buyer': {'buyerEmail': 'private@example.com'},
        }})

    client = AmazonSPAPIClient(Auth(), endpoint='https://sandbox.sellingpartnerapi-na.amazon.com',
                               http=httpx.Client(transport=httpx.MockTransport(reply)))
    order = AmazonOrdersSandbox(client).get_order()
    assert seen[0].url.path == '/orders/2026-01-01/orders/114-9876543-1234567'
    assert seen[0].url.params['includedData'] == 'RECIPIENT,PROCEEDS,FULFILLMENT'
    assert order.amazon_order_id == '114-9876543-1234567'
    assert order.order_status == 'UNSHIPPED'
    assert order.marketplace_id == 'ATVPDKIKX0DER'
    assert 'private@example.com' not in order.model_dump_json()


def test_missing_order_payload_is_not_reported_as_success():
    from app.services.amazon_orders import AmazonOrdersSandbox
    class Client:
        def request(self, *_args, **_kwargs):
            return {'orders': []}

    with pytest.raises(ValueError, match='order'):
        AmazonOrdersSandbox(Client()).get_order()


@pytest.mark.parametrize('mode,endpoint', [
    ('production', 'https://sellingpartnerapi-na.amazon.com'),
    ('sandbox', 'https://unexpected.example.com'),
])
def test_smoke_rejects_production_or_unknown_endpoint(mode, endpoint):
    settings = AmazonSettings('id', 'secret', 'refresh', endpoint=endpoint, mode=mode)
    with pytest.raises(ValueError, match='Sandbox'):
        settings.require_sandbox()


def test_smoke_output_contains_only_safe_order_summary():
    from scripts.test_sp_api_sandbox import run_smoke
    lines = []
    settings = AmazonSettings('id', 'private-secret', 'private-refresh', mode='sandbox')

    class Auth:
        def get_access_token(self):
            return 'private-token'

    class Client:
        def request(self, *_args, **_kwargs):
            return {'order': {'orderId': '114-9876543-1234567',
                    'createdTime': '2025-03-10T14:00:00Z',
                    'salesChannel': {'marketplaceId': 'ATVPDKIKX0DER'},
                    'fulfillment': {'fulfillmentStatus': 'UNSHIPPED'},
                    'buyer': {'buyerEmail': 'private@example.com'}}}

    order = run_smoke(settings, auth=Auth(), client=Client(), emit=lines.append)
    assert order.amazon_order_id == '114-9876543-1234567'
    displayed = '\n'.join(lines)
    assert 'Sandbox' in displayed
    assert '114-9876543-1234567' in displayed
    for forbidden in ('private-token', 'private-secret', 'private-refresh', 'private@example.com'):
        assert forbidden not in displayed
