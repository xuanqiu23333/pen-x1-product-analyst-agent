from app.schemas.state import AnalysisState
from app.skills.technical_risk import run_technical_risk
from app.skills.lifecycle_risk import run_lifecycle_risk
from app.skills.swot_decision import run_swot_decision
from app.skills.report_generation import run_report_generation

class CountingProvider:
    def __init__(self): self.calls=[]
    def complete_json(self, task, payload): self.calls.append(task); return {}

def test_real_risk_and_decision_skills_call_provider_but_report_stays_deterministic():
    state=AnalysisState()
    provider=CountingProvider()
    run_technical_risk(state, provider, 'REAL')
    run_lifecycle_risk(state, provider, 'REAL')
    run_swot_decision(state, provider, 'REAL')
    report=run_report_generation(state, provider, 'REAL')
    assert len(provider.calls) == 3
    assert report['title'] == 'PEN-X1 Real VOC Smoke Report'
