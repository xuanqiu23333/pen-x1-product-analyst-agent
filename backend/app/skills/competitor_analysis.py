from app.schemas.state import AnalysisState
from app.schemas.models import Evidence
from app.services.data_loader import load_json

def run_competitor_analysis(state: AnalysisState, data_root) -> list[dict]:
    rows = load_json(data_root, "competitors/competitors.json")
    for row in rows:
        state.add_evidence(Evidence(id=f"ev-competitor-{row['brand'].lower()}", source=row["source"], content=f"{row['brand']} {row['model']} fixture: battery {row['battery']}, price {row['price']}.", data_nature="PUBLIC_FIXTURE", confidence="MEDIUM"))
    return rows
