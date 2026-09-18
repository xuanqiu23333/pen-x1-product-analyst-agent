"""Orders static sandbox operation; HTTP and LWA remain in the shared client."""

from app.schemas.amazon_orders import AmazonOrderSummary
from app.services.amazon_sp_api_client import AmazonSPAPIClient


class AmazonOrdersSandbox:
    ORDER_ID = '114-9876543-1234567'
    INCLUDED_DATA = 'RECIPIENT,PROCEEDS,FULFILLMENT'

    def __init__(self, client: AmazonSPAPIClient):
        self.client = client

    def get_order(self) -> AmazonOrderSummary:
        payload = self.client.request(
            'GET', f'/orders/2026-01-01/orders/{self.ORDER_ID}',
            params={'includedData': self.INCLUDED_DATA}, operation='getOrder',
        )
        order = payload.get('order') if isinstance(payload, dict) else None
        if not isinstance(order, dict) or not order.get('orderId'):
            raise ValueError('Amazon Orders 响应缺少 order。')
        fulfillment = order.get('fulfillment') or {}
        channel = order.get('salesChannel') or {}
        return AmazonOrderSummary(
            amazon_order_id=order['orderId'], purchase_date=order.get('createdTime'),
            last_update_date=order.get('lastUpdatedTime'),
            order_status=fulfillment.get('fulfillmentStatus'),
            fulfillment_channel=fulfillment.get('fulfilledBy'),
            sales_channel=channel.get('channelName'), marketplace_id=channel.get('marketplaceId'),
        )
