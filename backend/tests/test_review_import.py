from pathlib import Path
import sqlite3
import warnings

from bs4 import MarkupResemblesLocatorWarning

from app.data_providers.review_csv_provider import ReviewCsvProvider
from app.services.review_cleaning import clean_text
from app.services.review_store import ReviewStore


HEADER = 'review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url,reviewer_email\n'


def test_import_cleans_and_keeps_only_review_fields(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    csv_text = HEADER + 'R123,B000000001,ThruNite Archer 2A C,4,<b>Good</b>,"<p>Bright&nbsp; beam</p>\nworks well",03/10/2025,yes,3,https://www.amazon.com/review/R123,private@example.com\n'
    run = store.import_csv(csv_text)
    rows = store.valid_reviews()
    assert (run['collected_reviews'], run['valid_reviews'], run['invalid_reviews']) == (1, 1, 0)
    assert rows[0]['review_id'] == 'R123'
    assert rows[0]['title'] == 'Good'
    assert rows[0]['review_text'] == 'Bright beam works well'
    assert rows[0]['review_date'] == '2025-03-10'
    assert rows[0]['source_type'] == 'IMPORTED_REAL'
    assert 'reviewer_email' not in rows[0]
    assert 'private@example.com' not in (tmp_path / 'reviews.sqlite3').read_bytes().decode('utf-8', errors='ignore')


def test_plain_source_url_is_normalized_without_html_parser_warning():
    with warnings.catch_warnings():
        warnings.simplefilter('error', MarkupResemblesLocatorWarning)
        assert clean_text('https://www.amazon.com/review/R123') == 'https://www.amazon.com/review/R123'


def test_invalid_rating_and_empty_body_do_not_enter_voc(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    csv_text = HEADER + 'R1,B000000001,ThruNite,6,T,Body,2025-03-10,no,0,,\nR2,B000000001,ThruNite,3,T,<p></p>,2025-03-10,no,0,,\n'
    run = store.import_csv(csv_text)
    assert (run['valid_reviews'], run['invalid_reviews']) == (0, 2)
    assert store.valid_reviews() == []
    assert store.stats()['coverage_level'] == 'NEED_DATA'


def test_external_id_and_hash_dedup_across_imports(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    first = HEADER + 'R123,B000000001,ThruNite,3,T,<p>Weak clip</p>,2025-03-10,yes,2,https://www.amazon.com/review/R123,\n'
    second = HEADER + 'R123,B000000001,ThruNite,3,T,Edited text,2025-03-10,yes,2,,\n,B000000001,ThruNite,3,T,Weak clip,2025-03-10,yes,2,,\n'
    assert store.import_csv(first)['valid_reviews'] == 1
    run = store.import_csv(second)
    assert run['duplicate_reviews'] == 2
    assert len(store.valid_reviews()) == 1
    assert store.stats()['raw_reviews'] == 3


def test_no_id_hash_dedup_uses_normalized_text(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    csv_text = HEADER + ',B000000001,ThruNite,2,T,<b>Bad</b>  battery,2025-03-10,no,0,,\n,B000000001,ThruNite,2,T,Bad battery,2025-03-10,no,0,,\n'
    run = store.import_csv(csv_text)
    assert (run['valid_reviews'], run['duplicate_reviews']) == (1, 1)
    assert len(store.valid_reviews()[0]['content_hash']) == 64


def test_distinct_stable_review_ids_are_not_collapsed_by_identical_text(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    csv_text = HEADER + 'R1,B000000001,ThruNite,4,T,Same text,2025-03-10,no,0,,\nR2,B000000001,ThruNite,4,T,Same text,2025-03-10,no,0,,\n'
    run = store.import_csv(csv_text)
    assert run['valid_reviews'] == 2
    assert run['duplicate_reviews'] == 0
    assert {row['review_id'] for row in store.valid_reviews()} == {'R1', 'R2'}


def test_existing_old_hash_index_is_migrated_before_new_import(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    store.import_csv(HEADER + 'R1,B000000001,ThruNite,4,T,Same text,2025-03-10,no,0,,\n')
    with sqlite3.connect(tmp_path / 'reviews.sqlite3') as connection:
        connection.execute("CREATE UNIQUE INDEX review_valid_hash ON review_raw(source_type, content_hash) WHERE raw_status='VALID'")
    run = store.import_csv(HEADER + 'R2,B000000001,ThruNite,4,T,Same text,2025-03-10,no,0,,\n')
    assert run['valid_reviews'] == 1


def test_real_provider_never_reads_demo_samples(tmp_path):
    real = ReviewCsvProvider(Path(__file__).resolve().parents[2] / 'data', mode='REAL', db_path=tmp_path / 'reviews.sqlite3')
    demo = ReviewCsvProvider(Path(__file__).resolve().parents[2] / 'data', mode='DEMO')
    assert real.get_reviews().data == []
    assert real.get_reviews().source_type == 'IMPORTED_REAL'
    assert len(demo.get_reviews().data) == 12
    assert demo.get_reviews().source_type == 'SAMPLE'


def test_real_csv_provider_can_import_without_changing_demo_source(tmp_path):
    root = Path(__file__).resolve().parents[2] / 'data'
    provider = ReviewCsvProvider(root, mode='REAL', db_path=tmp_path / 'reviews.sqlite3')
    csv_text = HEADER + 'R1,B000000001,ThruNite,4,T,Useful beam,2025-03-10,yes,1,,\n'
    assert provider.import_csv(csv_text)['valid_reviews'] == 1
    assert provider.get_reviews().data[0]['review_id'] == 'R1'
    assert ReviewCsvProvider(root, mode='DEMO').get_reviews().source_type == 'SAMPLE'


def test_coverage_and_product_counts_count_only_valid_real_rows(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    csv_text = HEADER + 'R1,B000000001,ThruNite Archer 2A C,5,T,Good light,2025-03-10,yes,1,,\nR2,B000000002,Streamlight MicroStream,4,T,Good clip,2025-03-11,no,0,,\n'
    store.import_csv(csv_text)
    stats = store.stats()
    assert stats['valid_reviews'] == 2
    assert stats['coverage_level'] == 'LOW_COVERAGE'
    assert stats['real_percent'] == 100
    assert stats['sample_percent'] == 0
    assert stats['products']['ThruNite Archer 2A C'] == 1
    assert stats['products']['Streamlight MicroStream'] == 1
