from pathlib import Path
from app.data_providers.base import ProviderResult
from app.services.data_loader import load_json, load_reviews

class FixtureProvider:
    """Offline deterministic provider used by DEMO_MODE and all fallbacks."""
    def __init__(self, data_root: Path): self.data_root = Path(data_root)

    def get_market_data(self) -> ProviderResult[list[dict]]:
        return ProviderResult(data=load_json(self.data_root, 'fixtures/market.json'), status='READY', source_type='FIXTURE', source_name='Market demonstration fixture')

    def get_competitor_data(self) -> ProviderResult[list[dict]]:
        return ProviderResult(data=load_json(self.data_root, 'competitors/competitors.json'), status='READY', source_type='FIXTURE', source_name='Competitor demonstration fixture')

    def get_reviews(self) -> ProviderResult[list[dict]]:
        return ProviderResult(data=load_reviews(self.data_root), status='READY', source_type='SAMPLE', source_name='Review CSV demonstration samples')
