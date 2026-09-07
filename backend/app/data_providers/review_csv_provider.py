from pathlib import Path
from app.data_providers.base import ProviderResult
from app.services.data_loader import load_reviews

class ReviewCsvProvider:
    def __init__(self, data_root: Path): self.data_root = Path(data_root)
    def get_reviews(self) -> ProviderResult[list[dict]]:
        return ProviderResult(data=load_reviews(self.data_root), status='READY', source_type='SAMPLE', source_name='Review CSV import')
