from app.schemas.models import Claim
from app.schemas.state import AnalysisState
from app.services.decision_engine import DecisionEngine
from app.validators.report_validator import validate_claims

def test_sample_market_and_open_technical_risk_produce_partial_and_conditional_go():
    state=AnalysisState(market={'research':{'sources':[{'status':'PUBLIC_FIXTURE'}]}}, voc={'review_count':3}, technical_risks=[{'severity':5,'status':'NEED_VERIFY','mitigation':'test'}], profit_analysis={'cost_status':{'fba':'UNKNOWN'}})
    decision=DecisionEngine().evaluate(state)
    assert decision['gates'][0]['status'] == 'PARTIAL'
    assert decision['decision'] == 'CONDITIONAL_GO'

def test_claim_without_fact_or_evidence_is_unsupported():
    result=validate_claims(AnalysisState(), [Claim(claim_id='c1', text='PEN-X1 具有 1000 流明输出', claim_type='product_spec', fact_ids=[], evidence_ids=[], status='UNSUPPORTED')])
    assert result.errors
