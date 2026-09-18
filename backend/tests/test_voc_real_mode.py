from pathlib import Path

from app.data_providers.review_csv_provider import ReviewCsvProvider
from app.schemas.state import AnalysisState
from app.services.review_store import ReviewStore
from app.skills.voc_analysis import run_voc_analysis


DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'
HEADER = 'review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url\n'


class SemanticProvider:
    def complete_json(self, task, payload):
        return {'items': [
            {'review_id': row['review_id'], 'sentiment': 'negative', 'usage_scenario': '随身携带',
             'purchase_reason': '日常照明',
             'aspects': [{'aspect': 'clip', 'sentiment': 'negative',
                          'pain_point': '口袋夹松动', 'severity': 'high'}]}
            for row in payload['reviews']
        ]}


def test_real_mode_with_no_imported_reviews_needs_data(tmp_path):
    provider = ReviewCsvProvider(DATA_ROOT, mode='REAL', db_path=tmp_path / 'review.sqlite3')
    state = AnalysisState()
    result = run_voc_analysis(state, DATA_ROOT, llm_provider=SemanticProvider(), mode='REAL', review_provider=provider)
    assert result['status'] == 'NEED_DATA'
    assert result['review_count'] == 0
    assert result['pain_points'] == []
    assert not any(item.id.startswith('ev-review-') for item in state.evidence)


def test_real_mode_without_explicit_review_provider_never_loads_samples(tmp_path):
    sample_dir = tmp_path / 'reviews'
    sample_dir.mkdir()
    (sample_dir / 'demo.csv').write_text('review_id,asin,product,rating,title,review_text,date,source\nSAMPLE,B000000001,Demo,2,T,Bad clip,2025-03-10,sample\n', encoding='utf-8')
    result = run_voc_analysis(AnalysisState(), tmp_path, llm_provider=None, mode='REAL')
    assert result['status'] == 'NEED_DATA'
    assert result['review_count'] == 0


def test_real_mode_rejects_a_sample_provider_even_if_injected():
    sample = ReviewCsvProvider(DATA_ROOT, mode='DEMO')
    result = run_voc_analysis(AnalysisState(), DATA_ROOT, llm_provider=None, mode='REAL', review_provider=sample)
    assert result['status'] == 'NEED_DATA'
    assert result['review_count'] == 0


def test_real_voc_uses_structured_output_and_python_aggregation(tmp_path):
    db_path = tmp_path / 'review.sqlite3'
    ReviewStore(db_path).import_csv(
        HEADER + 'R123,B000000001,ThruNite,2,Clip,Loose clip,2025-03-10,yes,7,https://www.amazon.com/review/R123\n'
        'R124,B000000002,Streamlight,4,Clip,Clip slips,2025-03-11,no,1,https://www.amazon.com/review/R124\n'
    )
    provider = ReviewCsvProvider(DATA_ROOT, mode='REAL', db_path=db_path)
    state = AnalysisState()
    result = run_voc_analysis(state, DATA_ROOT, llm_provider=SemanticProvider(), mode='REAL', review_provider=provider)
    point = result['pain_points'][0]
    assert result['status'] == 'COMPLETED'
    assert result['classification_source'] == 'LLM_STRUCTURED'
    assert result['review_count'] == 2
    assert point['mentions'] == 2
    assert point['frequency'] == 1.0
    assert point['avg_rating'] == 3.0
    assert point['product_distribution'] == {'ThruNite': 1, 'Streamlight': 1}
    assert point['evidence_review_ids'] == ['ev-review-R123', 'ev-review-R124']
    assert point['usage_scenarios'] == ['随身携带']
    assert point['purchase_reasons'] == ['日常照明']
    evidence = next(item for item in state.evidence if item.id == 'ev-review-R123')
    assert evidence.data_nature == 'IMPORTED_DATA'
    assert evidence.source_type == 'IMPORTED_REAL'
    assert evidence.asin == 'B000000001'
    assert evidence.rating == 2
    assert evidence.review_date == '2025-03-10'
    assert evidence.content == 'Loose clip'
    assert evidence.helpful_votes == 7
    assert evidence.source_url == 'https://www.amazon.com/review/R123'
    assert evidence.retrieved_at


def test_real_reviews_without_deepseek_do_not_use_rule_fallback(tmp_path):
    db_path = tmp_path / 'review.sqlite3'
    ReviewStore(db_path).import_csv(HEADER + 'R1,B000000001,ThruNite,2,T,Bad battery,2025-03-10,no,0,\n')
    provider = ReviewCsvProvider(DATA_ROOT, mode='REAL', db_path=db_path)
    result = run_voc_analysis(AnalysisState(), DATA_ROOT, llm_provider=None, mode='REAL', review_provider=provider)
    assert result['status'] == 'NEED_LLM'
    assert result['review_count'] == 1
    assert result['pain_points'] == []


def test_real_voc_rejects_unknown_review_ids_from_model(tmp_path):
    db_path = tmp_path / 'review.sqlite3'
    ReviewStore(db_path).import_csv(HEADER + 'R1,B000000001,ThruNite,2,T,Bad battery,2025-03-10,no,0,\n')
    provider = ReviewCsvProvider(DATA_ROOT, mode='REAL', db_path=db_path)

    class InventedProvider:
        def complete_json(self, task, payload):
            return {'items': [{'review_id': 'INVENTED', 'sentiment': 'negative',
                               'usage_scenario': None, 'purchase_reason': None, 'aspects': []}]}

    result = run_voc_analysis(AnalysisState(), DATA_ROOT, llm_provider=InventedProvider(), mode='REAL', review_provider=provider)
    assert result['status'] == 'NEED_LLM'
    assert result['pain_points'] == []
