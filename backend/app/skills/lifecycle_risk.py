from app.schemas.state import AnalysisState
from app.schemas.models import RiskCard

def run_lifecycle_risk(state: AnalysisState) -> list[dict]:
    cards = [
      RiskCard(risk_id="eol-compatibility", stage="Mass Production", module="EOL test", risk="Five-battery compatibility cannot rely on impractical manual testing of every consumer cell.", cause="Many form-factor and electrical combinations", trigger="End-of-line coverage gap", impact="Field compatibility escapes", severity=4, probability=None, detectability=3, evidence_ids=["ev-project-brief"], validation_method="Standardized battery simulator and extreme-dimension fixtures", mitigation="Add Five-Battery Compatibility EOL test with controlled fixtures", status="NEED_VERIFY"),
      RiskCard(risk_id="lithium-shipping", stage="Transport", module="Compliance", risk="A SKU containing 14500 cells requires external shipping-compliance verification.", cause="Lithium battery transport requirements", trigger="Battery-included SKU", impact="Shipment delay or listing restrictions", severity=5, probability=None, detectability=2, evidence_ids=["ev-project-brief"], validation_method="External compliance review for the exact SKU and route", mitigation="Keep battery-included SKU gated until verification", status="NEED_VERIFY"),
      RiskCard(risk_id="listing-clarity", stage="Amazon Listing", module="Consumer communication", risk="Customers may misunderstand performance differences across batteries.", cause="Multiple power configurations", trigger="Ambiguous listing or instructions", impact="Returns and negative reviews", severity=4, probability=None, detectability=3, evidence_ids=["ev-review-str-3"], validation_method="Listing comprehension test and support-content review", mitigation="Battery-specific performance table and clear insertion guidance", status="NEED_VERIFY")
    ]
    return [card.model_dump() | {"risk_score": card.risk_score} for card in cards]
