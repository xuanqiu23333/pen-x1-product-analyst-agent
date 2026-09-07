from app.schemas.state import AnalysisState
from app.schemas.models import Evidence

UNKNOWN_PARAMETERS = ["maximum lumen", "per-battery output", "runtime", "IP rating", "weight", "dimensions", "thermal rise", "certification status"]

def run_material_check(state: AnalysisState) -> dict:
    confirmed = [fact.name for fact in state.facts]
    state.add_evidence(Evidence(id="ev-project-brief", source="PEN-X1 project brief", content="Target price, five battery configurations, BOOST driver, battery identification, mechanical compensation and BOM.", data_nature="FACT", confidence="HIGH"))
    return {"confirmed": confirmed, "unknown": UNKNOWN_PARAMETERS, "need_verify": UNKNOWN_PARAMETERS, "external_research_required": ["market demand", "competitor specifications", "VOC"]}
