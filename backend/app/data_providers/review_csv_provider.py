from pathlib import Path
from app.data_providers.base import ProviderResult
from app.services.data_loader import load_reviews
from app.services.review_store import ReviewStore

class ReviewCsvProvider:
    def __init__(self, data_root: Path, mode: str = 'DEMO', db_path: Path | None = None):
        self.data_root = Path(data_root)
        self.mode = mode.upper()
        self.store = ReviewStore(db_path or self.data_root / 'reviews_real' / 'reviews.sqlite3')

    def import_csv(self, csv_text: str) -> dict:
        if self.mode != 'REAL':
            raise ValueError('只允许向真实评论数据层导入 CSV。')
        return self.store.import_csv(csv_text)

    def get_reviews(self) -> ProviderResult[list[dict]]:
        if self.mode == 'REAL':
            rows = self.store.valid_reviews()
            return ProviderResult(data=rows, status='LIVE' if rows else 'NEED_DATA',
                                  source_type='REAL_REVIEW',
                                  source_name='真实评论（CSV、Bright Data 或 Apify）',
                                  retrieved_at=self.store.stats()['last_collected'] or '')
        return ProviderResult(data=load_reviews(self.data_root), status='READY', source_type='SAMPLE', source_name='Review CSV import')
