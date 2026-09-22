import json
import urllib.request

import pytest
from pydantic import ValidationError

from app.data_providers.review_csv_provider import ReviewCsvProvider
from app.llm import deepseek_provider
from app.schemas.state import AnalysisState
from app.services.review_store import ReviewStore
from app.skills.voc_analysis import RealSemanticReview, run_voc_analysis


HEADER = 'review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url\n'


def _run(tmp_path, items, review_count=1):
    db_path = tmp_path / 'reviews.sqlite3'
    rows = [
        f'R{index},B00000000{index},Product {index},4,Title {index},Review text {index},2025-03-10,yes,0,\n'
        for index in range(1, review_count + 1)
    ]
    ReviewStore(db_path).import_csv(HEADER + ''.join(rows))

    class Provider:
        def complete_json(self, task, payload):
            return {'items': items}

    return run_voc_analysis(
        AnalysisState(), tmp_path, Provider(), 'REAL',
        ReviewCsvProvider(tmp_path, mode='REAL', db_path=db_path),
    )


def test_real_semantic_review_defaults_optional_fields_and_aspects():
    item = RealSemanticReview.model_validate({'review_id': 'R1', 'sentiment': 'positive'})
    assert item.usage_scenario is None
    assert item.purchase_reason is None
    assert item.aspects == []


def test_positive_aspect_allows_null_pain_point():
    item = RealSemanticReview.model_validate({
        'review_id': 'R1', 'sentiment': 'positive',
        'aspects': [{'aspect': 'brightness', 'sentiment': 'positive',
                     'pain_point': None, 'severity': 'low'}],
    })
    assert item.aspects[0].pain_point is None


def test_negative_aspect_rejects_null_pain_point():
    with pytest.raises(ValidationError):
        RealSemanticReview.model_validate({
            'review_id': 'R1', 'sentiment': 'negative',
            'aspects': [{'aspect': 'clip', 'sentiment': 'negative',
                         'pain_point': None, 'severity': 'high'}],
        })


@pytest.mark.parametrize(('items', 'missing', 'extra', 'duplicate'), [
    ([], ['R1'], [], []),
    ([{'review_id': 'R1', 'sentiment': 'neutral'},
      {'review_id': 'EXTRA', 'sentiment': 'neutral'}], [], ['EXTRA'], []),
    ([{'review_id': 'R1', 'sentiment': 'neutral'},
      {'review_id': 'R1', 'sentiment': 'neutral'}], ['R2'], [], ['R1']),
])
def test_review_id_integrity_returns_safe_diagnostic(tmp_path, items, missing, extra, duplicate):
    count = 2 if duplicate else 1
    result = _run(tmp_path, items, count)
    diagnostic = result['llm_diagnostic']
    assert result['status'] == 'NEED_LLM'
    assert diagnostic['failure_stage'] == 'REVIEW_ID_INTEGRITY'
    assert diagnostic['missing_review_ids'] == missing
    assert diagnostic['extra_review_ids'] == extra
    assert diagnostic['duplicate_review_ids'] == duplicate


def test_invalid_aspect_enum_returns_pydantic_diagnostic(tmp_path):
    result = _run(tmp_path, [{
        'review_id': 'R1', 'sentiment': 'negative',
        'aspects': [{'aspect': 'invented', 'sentiment': 'negative',
                     'pain_point': 'bad', 'severity': 'high'}],
    }])
    diagnostic = result['llm_diagnostic']
    assert diagnostic['failure_stage'] == 'PYDANTIC_VALIDATION'
    assert diagnostic['exception_type'] == 'ValidationError'
    assert diagnostic['validation_errors']
    assert all(set(item) <= {'location', 'type', 'message'} for item in diagnostic['validation_errors'])


def test_unexpected_exception_is_not_silently_swallowed(tmp_path):
    db_path = tmp_path / 'reviews.sqlite3'
    ReviewStore(db_path).import_csv(
        HEADER + 'R1,B000000001,Product,4,Title,Review text,2025-03-10,yes,0,\n')

    class BrokenProvider:
        def complete_json(self, task, payload):
            raise RuntimeError('safe failure')

    result = run_voc_analysis(
        AnalysisState(), tmp_path, BrokenProvider(), 'REAL',
        ReviewCsvProvider(tmp_path, mode='REAL', db_path=db_path),
    )
    assert result['status'] == 'NEED_LLM'
    assert result['llm_diagnostic']['failure_stage'] == 'UNKNOWN'
    assert result['llm_diagnostic']['exception_type'] == 'RuntimeError'
    assert result['llm_diagnostic']['safe_message'] == 'safe failure'


def test_deepseek_non_json_content_raises_distinct_safe_error(monkeypatch):
    envelope = {'choices': [{'message': {'content': 'not-json'}}]}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(envelope).encode()

    monkeypatch.setattr(urllib.request, 'urlopen', lambda request, timeout: Response())
    with pytest.raises(deepseek_provider.DeepSeekJSONError) as caught:
        deepseek_provider.DeepSeekProvider('secret-never-print', 'deepseek-chat').complete_json('task', {})
    assert caught.value.failure_stage == 'MODEL_CONTENT_JSON_PARSE'
    assert 'secret-never-print' not in str(caught.value)
