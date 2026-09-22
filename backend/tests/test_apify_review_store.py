from app.services.review_cleaning import (
    REAL_REVIEW_SOURCE_TYPES,
    normalize_apify_review,
)
from app.services.review_store import ReviewStore


COMPETITOR = {
    'brand': 'Streamlight', 'model': 'MicroStream 66318',
    'asin': 'B00143JZ08',
    'amazon_url': 'https://www.amazon.com/dp/B00143JZ08',
    'marketplace': 'US',
}
CSV_HEADER = 'review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url\n'


def _apify_row(review_id='RIGZGOCR0K67Y', text='Compact and reliable.'):
    return {
        'statusCode': 200,
        'statusMessage': 'FOUND',
        'asin': 'B00143JZ08',
        'productTitle': 'Streamlight MicroStream 66318',
        'currentPage': 1,
        'domainCode': 'com',
        'reviewId': review_id,
        'text': text,
        'date': 'Reviewed in the United States on May 10, 2024',
        'rating': '5.0 out of 5 stars',
        'title': 'Small dependable light',
        'userName': 'Private Person',
        'numberOfHelpful': 2,
        'variationId': 'B00143JZ08',
        'verified': True,
        'profilePath': '/gp/profile/private',
    }


def _kestrel_row(review_id='R21JW8SCU5RW9N', text='Compact and reliable.'):
    return {
        'type': 'review',
        'asin': 'B00143JZ08',
        'domain': 'com',
        'product_title': 'Streamlight 66318 MicroStream Pocket Flashlight, Black',
        'review_id': review_id,
        'rating': 5,
        'title': None,
        'text': text,
        'author': 'Private Person',
        'date_text': 'June 27, 2026',
        'verified': True,
        'helpful_votes': 2,
        'url': f'https://www.amazon.com/gp/customer-reviews/{review_id}',
        'fetched_at': '2026-09-21T09:15:10+00:00',
    }


def test_official_apify_output_maps_only_safe_review_fields():
    normalized, valid = normalize_apify_review(_apify_row(), COMPETITOR)

    assert valid is True
    assert normalized['external_review_id'] == 'RIGZGOCR0K67Y'
    assert normalized['asin'] == 'B00143JZ08'
    assert normalized['product_name'] == 'Streamlight MicroStream 66318'
    assert normalized['marketplace'] == 'US'
    assert normalized['rating'] == 5
    assert normalized['title'] == 'Small dependable light'
    assert normalized['review_text'] == 'Compact and reliable.'
    assert normalized['review_date'] == '2024-05-10'
    assert normalized['verified_purchase'] == 1
    assert normalized['helpful_votes'] == 2
    assert normalized['review_url'] is None
    assert normalized['product_url'] == COMPETITOR['amazon_url']
    assert normalized['source_type'] == 'APIFY_REAL'
    assert not {'userName', 'profilePath'} & normalized.keys()


def test_penalty_or_malformed_actor_item_is_invalid():
    normalized, valid = normalize_apify_review(
        {'statusCode': 404, 'statusMessage': 'NOT_FOUND', 'asin': 'B00143JZ08'},
        COMPETITOR,
    )

    assert valid is False
    assert normalized['review_text'] is None


def test_kestrel_output_maps_review_url_and_drops_author_identity():
    normalized, valid = normalize_apify_review(_kestrel_row(), COMPETITOR)

    assert valid is True
    assert normalized['external_review_id'] == 'R21JW8SCU5RW9N'
    assert normalized['product_name'] == 'Streamlight 66318 MicroStream Pocket Flashlight, Black'
    assert normalized['review_date'] == '2026-06-27'
    assert normalized['helpful_votes'] == 2
    assert normalized['review_url'] == (
        'https://www.amazon.com/gp/customer-reviews/R21JW8SCU5RW9N'
    )
    assert normalized['product_url'] == COMPETITOR['amazon_url']
    assert normalized['collected_at'] == '2026-09-21T09:15:10+00:00'
    assert 'author' not in normalized


def test_apify_review_is_persisted_as_valid_with_run_metadata(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')

    result = store.import_records(
        [_apify_row()], 'APIFY_REAL', 'APIFY_API', competitors=[COMPETITOR],
        requested_reviews=10, target_products=1, provider='APIFY',
        actor_run_id='actor-run-1', dataset_id='dataset-1', status='COMPLETED',
    )
    latest = store.latest_collection('APIFY_API')
    row = store.valid_reviews()[0]

    assert result['valid_reviews'] == 1
    assert row['source_type'] == 'APIFY_REAL'
    assert row['raw_status'] == 'VALID'
    assert latest['provider'] == 'APIFY'
    assert latest['actor_run_id'] == 'actor-run-1'
    assert latest['dataset_id'] == 'dataset-1'


def test_external_id_deduplicates_across_brightdata_and_apify(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    store.import_records([{
        'review_id': 'SAME-ID', 'asin': 'B00143JZ08',
        'product_name': 'Streamlight MicroStream 66318', 'rating': 5,
        'review_title': 'Title', 'review_text': 'Original text',
        'review_date': '2024-05-10', 'verified_purchase': True,
        'helpful_votes': 2,
    }], 'BRIGHTDATA_REAL', 'BRIGHTDATA_API', competitors=[COMPETITOR])

    result = store.import_records(
        [_apify_row(review_id='SAME-ID', text='Changed text')],
        'APIFY_REAL', 'APIFY_API', competitors=[COMPETITOR],
    )

    assert result['duplicate_reviews'] == 1
    assert len(store.valid_reviews()) == 1


def test_content_hash_deduplicates_csv_and_apify_without_review_id(tmp_path):
    store = ReviewStore(tmp_path / 'reviews.sqlite3')
    csv = CSV_HEADER + (
        ',B00143JZ08,Streamlight MicroStream 66318,5,T,Compact and reliable.,'
        '2024-05-10,yes,2,\n'
    )
    assert store.import_csv(csv)['valid_reviews'] == 1

    result = store.import_records(
        [_apify_row(review_id='')], 'APIFY_REAL', 'APIFY_API', competitors=[COMPETITOR]
    )

    assert result['duplicate_reviews'] == 1
    assert len(store.valid_reviews()) == 1
    assert REAL_REVIEW_SOURCE_TYPES == {
        'IMPORTED_REAL', 'BRIGHTDATA_REAL', 'APIFY_REAL'
    }
