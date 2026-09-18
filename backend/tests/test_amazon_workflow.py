from pathlib import Path

from app.schemas.models import Evidence, Fact
from app.services.amazon_auth import AmazonSettings
from app.workflow.runner import AnalysisRunner


DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'


def test_real_analysis_consumes_production_fact_evidence_without_mixing_review_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(AnalysisRunner, '_try_official_sources', lambda self, state, status: None)
    snapshot = {
        'summary': {'status': 'COMPLETED', 'mode': 'production', 'live_records': 3,
                    'catalog_records': 1, 'pricing_records': 1, 'feedback_topics': 1},
        'products': [{'asin': 'B000000001', 'brand': 'ThruNite', 'model': 'Archer 2A C',
                      'status': 'LIVE',
                      'catalog': {'title': 'Live Torch', 'status': 'LIVE'},
                      'pricing': {'listing_price': 23.99, 'currency': 'USD', 'status': 'LIVE'},
                      'feedback': [{'topic': 'Battery', 'sentiment': 'negative', 'mentions': 3,
                                    'star_rating_impact': -0.7, 'trend': [], 'status': 'LIVE'}]}],
        'facts': [Fact(id='amazon-B000000001-title', category='competitor', name='商品标题',
                       value='Live Torch', source_type='AMAZON_SP_API',
                       data_nature='PUBLIC_DATA').model_dump()],
        'evidence': [Evidence(id='ev-amazon-feedback-B000000001-negative-1',
                              source='Amazon Customer Feedback API', content='Battery: 3 mentions',
                              source_type='AMAZON_CUSTOMER_FEEDBACK',
                              data_nature='PUBLIC_DATA').model_dump()],
    }
    settings = AmazonSettings('id', 'secret', 'refresh', mode='production', real_data_enabled=True)
    runner = AnalysisRunner(DATA_ROOT, output_dir=tmp_path, amazon_snapshot=snapshot,
                            amazon_settings=settings)
    real = runner.run('REAL')
    assert real.fact_by_id('amazon-B000000001-title').value == 'Live Torch'
    assert any(row.get('asin') == 'B000000001' and row['price'] == 23.99 for row in real.competitors)
    assert real.voc['review_count'] == 12
    assert real.voc['amazon_feedback_topics'] == 1
    assert real.voc['amazon_feedback_mentions'] == 3
    assert any('ev-amazon-feedback-B000000001-negative-1' in item['voc_evidence']
               for item in real.opportunities)
    assert 'Amazon SP-API' in real.report['markdown']
    assert real.decision['gates'][0]['status'] == 'PARTIAL'
    demo = runner.run_demo()
    assert demo.fact_by_id('amazon-B000000001-title') is None
