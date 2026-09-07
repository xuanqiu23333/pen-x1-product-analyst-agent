from app.schemas.state import AnalysisState
from app.services.profit_calculator import calculate_profit_matrix

def run_profit_analysis(state: AnalysisState) -> dict:
    bom = state.fact_by_id("bom_rmb").value
    return {"currency_note":"All price and return-rate combinations are SCENARIO inputs, not market facts.", "cost_status":{"amazon_fee":"UNKNOWN", "fba":"UNKNOWN", "freight":"UNKNOWN", "advertising":"UNKNOWN", "tariff":"UNKNOWN"}, "without_battery": [cell.model_dump() for cell in calculate_profit_matrix(bom["without_battery"])], "with_battery": [cell.model_dump() for cell in calculate_profit_matrix(bom["with_battery"])]}
