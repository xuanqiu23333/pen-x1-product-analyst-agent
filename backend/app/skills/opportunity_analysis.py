from app.schemas.state import AnalysisState
from app.schemas.models import Opportunity

def run_opportunity_analysis(state: AnalysisState) -> list[dict]:
    battery_evidence = [point["evidence_review_ids"][0] for point in state.voc.get("pain_points", []) if point["aspect"] == "battery"]
    status = "NEED_VERIFY" if not battery_evidence else "INFERRED"
    return [Opportunity(id="opp-power-flexibility", title="Supply flexibility candidate opportunity", user_problem="Users may need commonly available power options away from charging.", voc_evidence=battery_evidence, competitor_gap=["ev-competitor-thrunite", "ev-competitor-streamlight"], product_capability="PEN-X1 FACT: 14500 / AA / AAA / 2AA / 2AAA support", market_evidence=["ev-market-1"], confidence="LOW", status=status, validation_needed=["Validate actual output and runtime for every battery configuration", "Validate customer comprehension of the power options"]).model_dump()]
