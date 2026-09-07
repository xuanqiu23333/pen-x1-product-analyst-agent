from app.schemas.state import AnalysisState
from app.schemas.models import Evidence
from app.services.data_loader import load_json

def run_market_research(state: AnalysisState, data_root) -> dict:
    rows = load_json(data_root, "fixtures/market.json")
    for index, row in enumerate(rows, 1):
        state.add_evidence(Evidence(id=f"ev-market-{index}", source=row["source"], content=f"{row['keyword']}: {row['price_range']}; sample size {row['product_count_sample']}.", data_nature="PUBLIC_FIXTURE", confidence="MEDIUM"))
    return {"price_segments": [row["price_range"] for row in rows], "common_features": sorted({feature for row in rows for feature in row["main_features"]}), "battery_patterns": [row["battery_type"] for row in rows], "customer_scenarios": ["EDC", "emergency backup", "light outdoor"], "market_observations": ["Demonstration fixture, not live Amazon data."], "sources": rows}
