from fastapi.testclient import TestClient

from app.api.routes import get_review_collection_service, get_review_store
from app.main import app
from app.services.review_store import ReviewStore


HEADER = 'review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url\n'


def test_import_endpoint_persists_and_reports_counts(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    app.dependency_overrides[get_review_store] = lambda: store
    try:
        client = TestClient(app)
        response = client.post('/api/reviews/import', content=HEADER + 'R1,B000000001,ThruNite,4,T,Good light,2025-03-10,yes,2,\n',
                               headers={'Content-Type': 'text/csv'})
        assert response.status_code == 201
        assert response.json()['valid_reviews'] == 1
        stats = client.get('/api/reviews/stats')
        assert stats.status_code == 200
        assert stats.json()['raw_reviews'] == 1
        assert stats.json()['products']['ThruNite'] == 1
    finally:
        app.dependency_overrides.clear()


def test_import_rejects_missing_columns_without_writing_rows(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    app.dependency_overrides[get_review_store] = lambda: store
    try:
        response = TestClient(app).post('/api/reviews/import', content='rating,review_text\n5,Good\n',
                                        headers={'Content-Type': 'text/csv'})
        assert response.status_code == 422
        assert store.stats()['raw_reviews'] == 0
    finally:
        app.dependency_overrides.clear()


def test_import_rejects_oversized_file(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    app.dependency_overrides[get_review_store] = lambda: store
    try:
        response = TestClient(app).post('/api/reviews/import', content=HEADER + 'x' * (5 * 1024 * 1024),
                                        headers={'Content-Type': 'text/csv'})
        assert response.status_code == 413
    finally:
        app.dependency_overrides.clear()


class FakeCollectionService:
    def __init__(self):
        self.received = []

    def collect_all_competitor_reviews(self, target=None):
        self.received.append(target)
        requested = 4 * target
        return {
            'status': 'COMPLETED', 'credential_configured': True,
            'target_products': 4, 'target_reviews': requested,
            'requested_reviews': requested, 'collected_reviews': 3,
            'valid_reviews': 2, 'duplicate_reviews': 1, 'invalid_reviews': 0,
            'failed_products': 0, 'products': [],
        }

    def latest_collection(self):
        return {
            'status': 'PRODUCT_URL_REQUIRED', 'credential_configured': True,
            'target_products': 4, 'target_reviews': 400,
            'requested_reviews': 0, 'collected_reviews': 0,
            'valid_reviews': 0, 'duplicate_reviews': 0, 'invalid_reviews': 0,
            'failed_products': 0, 'products': [],
        }


def test_collect_endpoint_forwards_bounded_target():
    service = FakeCollectionService()
    app.dependency_overrides[get_review_collection_service] = lambda: service
    try:
        response = TestClient(app).post(
            '/api/reviews/collect', json={'max_reviews_per_product': 100}
        )
        assert response.status_code == 200
        assert response.json()['requested_reviews'] == 400
        assert service.received == [100]
    finally:
        app.dependency_overrides.clear()


def test_collect_endpoint_defaults_to_one_hundred_without_body():
    service = FakeCollectionService()
    app.dependency_overrides[get_review_collection_service] = lambda: service
    try:
        response = TestClient(app).post('/api/reviews/collect')
        assert response.status_code == 200
        assert service.received == [100]
    finally:
        app.dependency_overrides.clear()


def test_collect_endpoint_rejects_unsafe_target():
    service = FakeCollectionService()
    app.dependency_overrides[get_review_collection_service] = lambda: service
    try:
        client = TestClient(app)
        assert client.post('/api/reviews/collect', json={'max_reviews_per_product': 0}).status_code == 422
        assert client.post('/api/reviews/collect', json={'max_reviews_per_product': 301}).status_code == 422
        assert service.received == []
    finally:
        app.dependency_overrides.clear()


def test_latest_collection_endpoint_is_read_only():
    service = FakeCollectionService()
    app.dependency_overrides[get_review_collection_service] = lambda: service
    try:
        response = TestClient(app).get('/api/reviews/collection/latest')
        assert response.status_code == 200
        assert response.json()['status'] == 'PRODUCT_URL_REQUIRED'
        assert service.received == []
    finally:
        app.dependency_overrides.clear()
