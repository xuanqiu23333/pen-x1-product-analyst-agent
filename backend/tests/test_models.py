from app.schemas.models import Fact, RiskCard


def test_unknown_fact_requires_no_invented_value():
    fact = Fact(id="unknown-lumen", category="product", name="max lumen", value=None, status="UNKNOWN")
    assert fact.value is None


def test_risk_score_is_unknown_without_probability():
    risk = RiskCard(risk_id="r1", stage="EVT", module="battery", risk="test", cause="test", trigger="test", impact="test", severity=4, probability=None, detectability=3, evidence_ids=[], validation_method="test", mitigation="test", status="NEED_VERIFY")
    assert risk.risk_score is None
