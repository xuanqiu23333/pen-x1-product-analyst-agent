from pathlib import Path
from app.workflow.runner import AnalysisRunner


DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


def test_demo_workflow_completes_all_ten_skills(tmp_path):
    state = AnalysisRunner(DATA_ROOT, output_dir=tmp_path).run_demo()
    assert len(state.skill_runs) == 10
    assert {run.status for run in state.skill_runs} == {"COMPLETED"}
    assert state.decision["decision"] == "CONDITIONAL_GO"
