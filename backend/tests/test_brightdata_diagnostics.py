import importlib.util
from pathlib import Path
from types import SimpleNamespace

from app.services.brightdata_client import BrightDataAPIError


SCRIPT_PATH = Path(__file__).resolve().parents[2] / 'scripts' / 'diagnose_brightdata_reviews.py'


def _load_script():
    spec = importlib.util.spec_from_file_location('diagnose_brightdata_reviews', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, trigger_results, rows=None):
        self.trigger_results = iter(trigger_results)
        self.inputs = []
        self.rows = rows or []
        self.status_calls = []
        self.download_calls = []
        self.settings = SimpleNamespace(
            poll_interval_seconds=0.01,
            max_poll_seconds=1.0,
        )

    def trigger_collection(self, inputs):
        self.inputs.append(inputs)
        result = next(self.trigger_results)
        if isinstance(result, Exception):
            raise result
        return result

    def get_snapshot_status(self, snapshot_id):
        self.status_calls.append(snapshot_id)
        return {'status': 'ready'}

    def download_snapshot(self, snapshot_id):
        self.download_calls.append(snapshot_id)
        return self.rows


def test_case_a_failure_prints_safe_diagnostics_and_stops_before_case_b():
    module = _load_script()
    error = BrightDataAPIError(
        400, 'invalid payload', False, error_code='validation_error',
        error_message='max_reviews is invalid', response_excerpt='safe excerpt',
    )
    client = FakeClient([error])
    output = []

    exit_code = module.run_diagnostics(client, output.append, sleep=lambda _: None)

    assert exit_code == 1
    assert len(client.inputs) == 1
    assert output == [
        'CASE_A=FAIL',
        'HTTP=400',
        'snapshot_id=',
        'error_code=validation_error',
        'error_message=max_reviews is invalid',
        'response_excerpt=safe excerpt',
    ]


def test_case_a_success_runs_case_b_ten_and_reports_only_field_names():
    module = _load_script()
    rows = [{
        'url': 'https://www.amazon.com/review/example',
        'product_name': 'Archer 2A C',
        'rating': 5,
        'review_text': 'Private body must not be printed',
        'author_name': 'Private Person',
    }]
    client = FakeClient(['s_official', 's_thrunite'], rows=rows)
    output = []

    exit_code = module.run_diagnostics(client, output.append, sleep=lambda _: None)

    assert exit_code == 0
    assert len(client.inputs) == 2
    assert client.inputs[0] == [{
        'url': 'https://www.amazon.com/Solar-Eclipse-Glasses-Certified-Viewing/dp/B08GB3QC1H',
        'reviews_to_not_include': [], 'max_reviews': 10, 'variation_specific': False,
    }]
    assert client.inputs[1] == [{
        'url': 'https://www.amazon.com/dp/B0CTCDPXFY/',
        'reviews_to_not_include': [], 'max_reviews': 10, 'variation_specific': True,
    }]
    assert client.status_calls == ['s_thrunite']
    assert client.download_calls == ['s_thrunite']
    assert 'CASE_A=PASS' in output
    assert 'CASE_B=PASS' in output
    assert 'snapshot_id=s_thrunite' in output
    assert 'actual_records=1' in output
    assert 'actual_fields=author_name,product_name,rating,review_text,url' in output
    serialized = '\n'.join(output)
    assert 'Private body' not in serialized
    assert 'Private Person' not in serialized
