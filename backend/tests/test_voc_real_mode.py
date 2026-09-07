from pathlib import Path
from app.schemas.state import AnalysisState
from app.skills.voc_analysis import run_voc_analysis

DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'

class SemanticProvider:
    def __init__(self): self.calls = []
    def complete_json(self, task, payload):
        self.calls.append(task)
        return {'items': [{'review_id': item['review_id'], 'sentiment':'negative', 'aspects':[{'aspect':'battery', 'sentiment':'negative', 'pain_point':'常见电池可获得性', 'severity':'medium'}]} for item in payload['reviews']]}

def test_real_voc_uses_injected_llm_and_python_frequency():
    provider = SemanticProvider()
    result = run_voc_analysis(AnalysisState(), DATA_ROOT, llm_provider=provider, mode='REAL')
    assert provider.calls
    assert result['classification_source'] == 'LLM_STRUCTURED'
    assert result['pain_points'][0]['mentions'] == result['review_count']
    assert result['pain_points'][0]['evidence_review_ids'][0].startswith('ev-review-')
