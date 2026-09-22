"""Shared contract for externally collected real-review providers."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ReviewCollectionProvider(Protocol):
    provider_name: str
    source_type: str
    source_name: str

    @property
    def status(self) -> str: ...

    def collect_product_reviews(self, product_url: str, asin: str,
                                product_name: str, max_reviews: int = 100) -> list[dict]: ...

    def collect_competitors(self, competitors: list[dict],
                            max_reviews_per_product: int = 100) -> dict: ...
