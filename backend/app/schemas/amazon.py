"""Normalized Amazon records; raw API payloads are not persisted."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AmazonCatalogRecord(BaseModel):
    asin: str
    title: str | None = None
    brand: str | None = None
    model: str | None = None
    product_type: str | None = None
    images: list[str] = Field(default_factory=list)
    sales_rank: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    marketplace_id: str
    source_type: str = 'AMAZON_SP_API'
    source_url: str
    retrieved_at: str
    status: str


class AmazonPricingRecord(BaseModel):
    asin: str
    listing_price: float | None = None
    currency: str | None = None
    offer_count: int | None = None
    buy_box_or_featured_offer: dict | None = None
    marketplace_id: str
    source_type: str = 'AMAZON_SP_API'
    source_url: str
    retrieved_at: str
    status: str


class AmazonFeedbackRecord(BaseModel):
    asin: str
    topic: str
    sentiment: str
    mentions: int | None = None
    star_rating_impact: float | None = None
    trend: list[dict] = Field(default_factory=list)
    marketplace_id: str
    source_type: str = 'AMAZON_CUSTOMER_FEEDBACK'
    data_nature: str = 'PUBLIC_DATA'
    source_url: str
    retrieved_at: str
    status: str


class AmazonProductSync(BaseModel):
    asin: str
    brand: str | None = None
    model: str | None = None
    catalog: AmazonCatalogRecord | None = None
    pricing: AmazonPricingRecord | None = None
    feedback: list[AmazonFeedbackRecord] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    status: str = 'PENDING'


class AmazonSyncSummary(BaseModel):
    run_id: str
    started_at: str
    finished_at: str
    status: str
    mode: str
    credential_configured: bool
    target_products: int = 0
    successful_products: int = 0
    failed_products: int = 0
    catalog_records: int = 0
    pricing_records: int = 0
    feedback_topics: int = 0
    api_requests: int = 0
    api_errors: int = 0
    rate_limit_events: int = 0
    live_records: int = 0
    fallback_records: int = 0
    rate_limits: dict[str, str] = Field(default_factory=dict)
    request_ids: list[str] = Field(default_factory=list)
    products: list[dict] = Field(default_factory=list)
