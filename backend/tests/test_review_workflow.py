from pathlib import Path

from app.llm.mock_provider import MockLLMProvider
from app.services.amazon_auth import AmazonSettings
from app.services.review_store import ReviewStore
from app.workflow.runner import AnalysisRunner


DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'
HEADER = 'review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url\n'


def test_real_workflow_uses_only_real_reviews_and_demo_remains_sample(tmp_path, monkeypatch):
    db_path = tmp_path / 'review.sqlite3'
    ReviewStore(db_path).import_csv(HEADER + 'REAL1,B000000001,ThruNite,2,T,Loose clip,2025-03-10,yes,1,\n')
    monkeypatch.setattr(AnalysisRunner, '_try_official_sources', lambda self, state, status: None)
    monkeypatch.setattr('app.workflow.runner.get_llm_provider',
                        lambda force_real=False: None if force_real else MockLLMProvider())
    runner = AnalysisRunner(DATA_ROOT, output_dir=tmp_path,
                            amazon_settings=AmazonSettings(mode='sandbox'), review_db_path=db_path)
    real = runner.run('REAL')
    assert real.voc['review_count'] == 1
    assert real.voc['status'] == 'NEED_LLM'
    assert real.project['data_provider_status']['评论数据']['source_type'] == 'REAL_REVIEW'
    assert any(item.id == 'ev-review-REAL1' and item.source_type == 'IMPORTED_REAL' for item in real.evidence)
    assert not any(item.data_nature == 'SAMPLE' for item in real.evidence)
    assert real.decision['gates'][0]['status'] == 'PENDING'
    assert '真实评论：1 条' in real.report['markdown']
    assert '示例评论：12 条' not in real.report['markdown']
    demo = runner.run_demo()
    assert demo.voc['review_count'] == 12
    assert demo.project['data_provider_status']['评论数据']['source_type'] == 'SAMPLE'


def test_real_workflow_merges_brightdata_and_csv_with_traceable_urls(tmp_path, monkeypatch):
    db_path = tmp_path / 'review.sqlite3'
    store = ReviewStore(db_path)
    store.import_csv(HEADER + 'CSV1,B000000001,ThruNite,3,T,Weak battery,2025-03-10,yes,1,https://www.amazon.com/review/CSV1\n')
    competitor = {
        'brand': 'ThruNite', 'model': 'Archer 2A C', 'asin': 'B000000001',
        'amazon_url': 'https://www.amazon.com/dp/B000000001', 'marketplace': 'US',
    }
    store.import_records([{
        'review_id': 'BD1', 'asin': 'B000000001', 'review_rating': 2,
        'review_title': 'Clip', 'review_text': 'Loose clip',
        'review_date': '2025-03-11', 'verified_purchase': True,
        'helpful_votes': 3,
    }], 'BRIGHTDATA_REAL', 'BRIGHTDATA_API', competitors=[competitor])
    monkeypatch.setattr(AnalysisRunner, '_try_official_sources', lambda self, state, status: None)
    monkeypatch.setattr('app.workflow.runner.get_llm_provider',
                        lambda force_real=False: None if force_real else MockLLMProvider())
    runner = AnalysisRunner(DATA_ROOT, output_dir=tmp_path,
                            amazon_settings=AmazonSettings(mode='sandbox'), review_db_path=db_path)

    real = runner.run('REAL')

    assert real.voc['review_count'] == 2
    review_evidence = [item for item in real.evidence if item.id.startswith('ev-review-')]
    assert {item.source_type for item in review_evidence} == {'IMPORTED_REAL', 'BRIGHTDATA_REAL'}
    assert not any(item.data_nature == 'SAMPLE' for item in real.evidence)
    brightdata = next(item for item in review_evidence if item.source_type == 'BRIGHTDATA_REAL')
    assert brightdata.review_url is None
    assert brightdata.source_url is None
    assert brightdata.product_url == competitor['amazon_url']
    assert brightdata.verified_purchase is True
    assert brightdata.helpful_votes == 3


def test_real_workflow_uses_apify_review_with_traceable_evidence_and_no_sample(
        tmp_path, monkeypatch):
    db_path = tmp_path / 'review.sqlite3'
    competitor = {
        'brand': 'Streamlight', 'model': 'MicroStream 66318',
        'asin': 'B00143JZ08',
        'amazon_url': 'https://www.amazon.com/dp/B00143JZ08', 'marketplace': 'US',
    }
    ReviewStore(db_path).import_records([{
        'statusCode': 200, 'statusMessage': 'FOUND', 'asin': 'B00143JZ08',
        'productTitle': 'Streamlight MicroStream 66318', 'reviewId': 'APIFY1',
        'text': 'Compact and reliable.',
        'date': 'Reviewed in the United States on May 10, 2024',
        'rating': '5.0 out of 5 stars', 'title': 'Small dependable light',
        'numberOfHelpful': 2, 'verified': True, 'domainCode': 'com',
        'userName': 'Private Person', 'profilePath': '/gp/profile/private',
    }], 'APIFY_REAL', 'APIFY_API', competitors=[competitor])
    monkeypatch.setattr(AnalysisRunner, '_try_official_sources', lambda self, state, status: None)
    monkeypatch.setattr('app.workflow.runner.get_llm_provider',
                        lambda force_real=False: None if force_real else MockLLMProvider())
    runner = AnalysisRunner(DATA_ROOT, output_dir=tmp_path,
                            amazon_settings=AmazonSettings(mode='sandbox'), review_db_path=db_path)

    real = runner.run('REAL')

    assert real.voc['review_count'] == 1
    assert real.voc['source_counts'] == {'APIFY_REAL': 1}
    assert any(item['source'] == 'Apify API 获取的真实 Amazon 评论'
               for item in real.voc['sources'])
    evidence = next(item for item in real.evidence if item.id == 'ev-review-APIFY1')
    assert evidence.source_type == 'APIFY_REAL'
    assert evidence.product_name == 'Streamlight MicroStream 66318'
    assert evidence.asin == 'B00143JZ08'
    assert evidence.rating == 5
    assert evidence.review_date == '2024-05-10'
    assert evidence.content == 'Compact and reliable.'
    assert evidence.verified_purchase is True
    assert evidence.helpful_votes == 2
    assert evidence.product_url == competitor['amazon_url']
    assert not any(item.data_nature == 'SAMPLE' for item in real.evidence)
    assert 'Apify API：1 条' in real.report['markdown']
