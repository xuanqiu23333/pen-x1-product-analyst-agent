"""Small, non-PII summary of an Orders API response."""

from pydantic import BaseModel


class AmazonOrderSummary(BaseModel):
    amazon_order_id: str
    purchase_date: str | None = None
    last_update_date: str | None = None
    order_status: str | None = None
    fulfillment_channel: str | None = None
    sales_channel: str | None = None
    marketplace_id: str | None = None
