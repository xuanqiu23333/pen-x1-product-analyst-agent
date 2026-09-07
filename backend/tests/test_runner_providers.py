from pathlib import Path
from app.workflow.runner import AnalysisRunner

DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'

def test_demo_run_records_fixture_and_csv_provider_statuses(tmp_path):
    state = AnalysisRunner(DATA_ROOT, output_dir=tmp_path).run_demo()
    statuses = state.project['data_provider_status']
    assert statuses['内部资料']['status'] == 'READY'
    assert statuses['市场数据']['source_type'] == 'FIXTURE'
    assert statuses['评论数据']['source_type'] == 'SAMPLE'
