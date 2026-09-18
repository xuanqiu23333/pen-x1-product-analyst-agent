from fastapi.testclient import TestClient

from app.api.routes import get_review_store
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
