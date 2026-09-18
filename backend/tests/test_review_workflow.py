from pathlib import Path

from app.llm.mock_provider import MockLLMProvider
from app.services.amazon_auth import AmazonSettings
from app.services.review_store import ReviewStore
from app.workflow.runner import AnalysisRunner


DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'
HEADER = 'review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url\n'


def test_real_workflow_uses_only_imported_reviews_and_demo_remains_sample(tmp_path, monkeypatch):
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
    assert real.project['data_provider_status']['评论数据']['source_type'] == 'IMPORTED_REAL'
    assert any(item.id == 'ev-review-REAL1' and item.source_type == 'IMPORTED_REAL' for item in real.evidence)
    assert not any(item.data_nature == 'SAMPLE' for item in real.evidence)
    assert real.decision['gates'][0]['status'] == 'PENDING'
    assert '真实导入评论：1 条' in real.report['markdown']
    assert '示例评论：12 条' not in real.report['markdown']
    demo = runner.run_demo()
    assert demo.voc['review_count'] == 12
    assert demo.project['data_provider_status']['评论数据']['source_type'] == 'SAMPLE'
