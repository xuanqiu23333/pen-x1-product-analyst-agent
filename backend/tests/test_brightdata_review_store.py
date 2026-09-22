import json
import sqlite3

from app.services.review_cleaning import (
    REAL_REVIEW_SOURCE_TYPES,
    normalize_brightdata_review,
)
from app.services.review_store import ReviewStore


CSV_HEADER = 'review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url\n'
CSV_R1 = CSV_HEADER + 'R1,B000000001,ThruNite Archer 2A C,4,Good,Useful beam,2025-03-10,yes,2,https://www.amazon.com/review/R1\n'

COMPETITOR = {
    'brand': 'ThruNite',
    'model': 'Archer 2A C',
    'asin': 'B000000001',
    'amazon_url': 'https://www.amazon.com/dp/B000000001',
    'marketplace': 'US',
}


def _brightdata_row(review_id='BR1', review_text='Loose clip'):
    return {
        'review_id': review_id,
        'review_rating': 2,
        'review_title': 'Clip issue',
        'review_text': review_text,
        'review_date': '2025-03-11',
        'verified_purchase': True,
        'helpful_votes': 5,
        'review_url': f'https://www.amazon.com/review/{review_id}',
        'author': 'Private Person',
        'profile': 'https://www.amazon.com/profile/private',
    }


def _observed_brightdata_row():
    """Minimal privacy-safe mirror of the confirmed CASE A response shape."""
    return {
        'asin': 'B08GB3QC1H',
        'rating': 5,
        'review_header': 'Reliable eclipse glasses',
        'review_text': 'Worked exactly as expected.',
        'review_posted_date': 'May 10, 2024',
        'review_id': 'R2YLUC2YWNK8PE',
        'is_verified': True,
        'helpful_count': 2,
        'url': 'https://www.amazon.com/dp/B08GB3QC1H',
        'product_name': 'Solar Eclipse Glasses',
        'timestamp': '2026-09-20T12:05:50.982Z',
        'author_id': 'PRIVATE-ID',
        'author_link': 'https://www.amazon.com/profile/private',
        'author_name': 'Private Person',
    }


def test_brightdata_normalization_maps_safe_fields_and_separates_urls():
    normalized, valid = normalize_brightdata_review(_brightdata_row(), COMPETITOR)

    assert valid is True
    assert normalized['external_review_id'] == 'BR1'
    assert normalized['source_type'] == 'BRIGHTDATA_REAL'
    assert normalized['review_url'] == 'https://www.amazon.com/review/BR1'
    assert normalized['source_url'] == 'https://www.amazon.com/review/BR1'
    assert normalized['product_url'] == COMPETITOR['amazon_url']
    assert normalized['asin'] == 'B000000001'
    assert normalized['product_name'] == 'ThruNite Archer 2A C'
    assert 'author' not in normalized
    assert 'profile' not in normalized


def test_missing_review_url_never_uses_product_url_as_source_url():
    raw = _brightdata_row()
    raw.pop('review_url')

    normalized, valid = normalize_brightdata_review(raw, COMPETITOR)

    assert valid is True
    assert normalized['review_url'] is None
    assert normalized['source_url'] is None
    assert normalized['product_url'] == COMPETITOR['amazon_url']


def test_confirmed_brightdata_schema_maps_fields_without_treating_product_url_as_review_url():
    normalized, valid = normalize_brightdata_review(_observed_brightdata_row(), {})

    assert valid is True
    assert normalized['external_review_id'] == 'R2YLUC2YWNK8PE'
    assert normalized['asin'] == 'B08GB3QC1H'
    assert normalized['product_name'] == 'Solar Eclipse Glasses'
    assert normalized['rating'] == 5
    assert normalized['title'] == 'Reliable eclipse glasses'
    assert normalized['review_text'] == 'Worked exactly as expected.'
    assert normalized['review_date'] == '2024-05-10'
    assert normalized['verified_purchase'] == 1
    assert normalized['helpful_votes'] == 2
    assert normalized['review_url'] is None
    assert normalized['source_url'] is None
    assert normalized['product_url'] == 'https://www.amazon.com/dp/B08GB3QC1H'
    assert normalized['collected_at'] == '2026-09-20T12:05:50.982000+00:00'
    assert not {'author_id', 'author_link', 'author_name'} & normalized.keys()


def test_store_uses_brightdata_timestamp_as_collected_at(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')

    result = store.import_records(
        [_observed_brightdata_row()], 'BRIGHTDATA_REAL', 'BRIGHTDATA_API',
        competitors=[], requested_reviews=1, target_products=1,
    )

    assert result['valid_reviews'] == 1
    assert store.valid_reviews()[0]['collected_at'] == '2026-09-20T12:05:50.982000+00:00'


def test_import_records_detects_external_id_duplicate_across_real_sources(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    assert store.import_csv(CSV_R1)['valid_reviews'] == 1
    duplicate = _brightdata_row(review_id='R1', review_text='Edited API text')

    result = store.import_records(
        [duplicate],
        source_type='BRIGHTDATA_REAL',
        source_name='BRIGHTDATA_API',
        competitors=[COMPETITOR],
        requested_reviews=1,
        target_products=1,
    )

    assert (result['valid_reviews'], result['duplicate_reviews']) == (0, 1)
    assert len(store.valid_reviews()) == 1
    assert store.stats()['raw_reviews'] == 2


def test_import_records_detects_hash_duplicate_across_real_sources(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    csv_without_id = CSV_HEADER + ',B000000001,ThruNite Archer 2A C,2,T,Loose clip,2025-03-11,yes,5,\n'
    assert store.import_csv(csv_without_id)['valid_reviews'] == 1
    raw = _brightdata_row(review_id='', review_text='Loose   clip')

    result = store.import_records(
        [raw], 'BRIGHTDATA_REAL', 'BRIGHTDATA_API', competitors=[COMPETITOR]
    )

    assert result['duplicate_reviews'] == 1
    assert len(store.valid_reviews()) == 1


def test_both_real_sources_are_returned_and_counted(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    store.import_csv(CSV_R1)
    store.import_records(
        [_brightdata_row()], 'BRIGHTDATA_REAL', 'BRIGHTDATA_API',
        competitors=[COMPETITOR], requested_reviews=1, target_products=1,
    )

    rows = store.valid_reviews()
    assert {row['source_type'] for row in rows} == {'IMPORTED_REAL', 'BRIGHTDATA_REAL'}
    assert store.stats()['valid_reviews'] == 2
    assert store.stats()['source_type'] == 'REAL_REVIEW'


def test_collection_run_persists_requested_failed_snapshot_and_products(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    product_summaries = [{
        'brand': 'ThruNite', 'model': 'Archer 2A C', 'status': 'COMPLETED',
        'requested_reviews': 5, 'collected_reviews': 1, 'valid_reviews': 1,
        'duplicate_reviews': 0, 'invalid_reviews': 0,
    }]

    result = store.import_records(
        [_brightdata_row()], 'BRIGHTDATA_REAL', 'BRIGHTDATA_API',
        competitors=[COMPETITOR], requested_reviews=5, target_products=1,
        failed_products=0, product_summaries=product_summaries,
        snapshot_id='s_test', status='COMPLETED',
    )
    latest = store.latest_collection()

    assert result['requested_reviews'] == 5
    assert latest['snapshot_id'] == 's_test'
    assert latest['products'] == product_summaries
    assert latest['failed_products'] == 0


def test_legacy_database_is_migrated_without_losing_review(tmp_path):
    db_path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(db_path) as connection:
        connection.executescript('''
            CREATE TABLE review_collection_run (
                run_id TEXT PRIMARY KEY, source TEXT NOT NULL, started_at TEXT NOT NULL,
                finished_at TEXT, target_products INTEGER NOT NULL DEFAULT 0,
                collected_reviews INTEGER NOT NULL DEFAULT 0, valid_reviews INTEGER NOT NULL DEFAULT 0,
                duplicate_reviews INTEGER NOT NULL DEFAULT 0, invalid_reviews INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL
            );
            CREATE TABLE review_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT, external_review_id TEXT, asin TEXT,
                product_name TEXT, marketplace TEXT, rating REAL, title TEXT, review_text TEXT,
                review_date TEXT, verified_purchase INTEGER, helpful_votes INTEGER,
                source_type TEXT NOT NULL, source_url TEXT, collected_at TEXT NOT NULL,
                content_hash TEXT, raw_status TEXT NOT NULL, collection_run_id TEXT NOT NULL
            );
        ''')
        connection.execute(
            "INSERT INTO review_collection_run VALUES(?,?,?,?,?,?,?,?,?,?)",
            ('old-run', 'CSV_IMPORT', '2025-03-10T00:00:00+00:00',
             '2025-03-10T00:00:01+00:00', 1, 1, 1, 0, 0, 'COMPLETED'),
        )
        connection.execute(
            "INSERT INTO review_raw(external_review_id,asin,product_name,marketplace,rating,title,review_text,review_date,verified_purchase,helpful_votes,source_type,source_url,collected_at,content_hash,raw_status,collection_run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('OLD1', 'B000000001', 'ThruNite Archer 2A C', 'US', 4, 'Good',
             'Legacy review', '2025-03-10', 1, 1, 'IMPORTED_REAL',
             'https://www.amazon.com/review/OLD1', '2025-03-10T00:00:00+00:00',
             'a' * 64, 'VALID', 'old-run'),
        )

    store = ReviewStore(db_path)
    rows = store.valid_reviews()
    with sqlite3.connect(db_path) as connection:
        run_columns = {row[1] for row in connection.execute('PRAGMA table_info(review_collection_run)')}
        review_columns = {row[1] for row in connection.execute('PRAGMA table_info(review_raw)')}

    assert rows[0]['review_id'] == 'OLD1'
    assert rows[0]['review_url'] == 'https://www.amazon.com/review/OLD1'
    assert {'requested_reviews', 'failed_products', 'product_summaries_json', 'snapshot_id'} <= run_columns
    assert {'review_url', 'product_url'} <= review_columns


def test_imported_record_never_persists_unlisted_personal_fields(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    raw = _brightdata_row()
    raw['reviewer_email'] = 'private@example.com'

    store.import_records([raw], 'BRIGHTDATA_REAL', 'BRIGHTDATA_API', competitors=[COMPETITOR])

    database_bytes = store.db_path.read_bytes().decode('utf-8', errors='ignore')
    assert 'Private Person' not in database_bytes
    assert 'private@example.com' not in database_bytes
    assert '/profile/private' not in database_bytes
