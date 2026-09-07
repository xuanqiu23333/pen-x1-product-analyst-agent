from fastapi.testclient import TestClient
from app.main import app


def test_demo_api_exposes_structured_run_and_report():
    client = TestClient(app)
    started = client.post('/api/analysis-runs', json={'mode':'DEMO'})
    assert started.status_code == 201
    run_id = started.json()['run_id']
    state = client.get(f'/api/analysis-runs/{run_id}')
    assert state.status_code == 200
    assert len(state.json()['skill_runs']) == 10
    report = client.get(f'/api/analysis-runs/{run_id}/report')
    assert report.status_code == 200
    assert 'PEN-X1' in report.json()['markdown']
