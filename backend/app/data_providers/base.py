from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generic, Protocol, TypeVar

T = TypeVar('T')

@dataclass
class ProviderResult(Generic[T]):
    data: T | None
    status: str
    source_type: str
    source_name: str
    source_url: str | None = None
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fallback_reason: str | None = None
    warnings: list[str] = field(default_factory=list)

class MarketDataProvider(Protocol):
    def get_market_data(self) -> ProviderResult[list[dict]]: ...

class CompetitorDataProvider(Protocol):
    def get_competitor_data(self) -> ProviderResult[list[dict]]: ...

class ReviewDataProvider(Protocol):
    def get_reviews(self) -> ProviderResult[list[dict]]: ...
