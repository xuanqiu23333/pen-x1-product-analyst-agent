from app.schemas.state import AnalysisState
from app.schemas.models import Evidence
from app.data_providers.fixture_provider import FixtureProvider

def run_competitor_analysis(state: AnalysisState, data_root, competitor_provider=None) -> list[dict]:
    result = competitor_provider.get_competitor_data() if competitor_provider else FixtureProvider(data_root).get_competitor_data()
    rows = result.data or []
    for row in rows:
        state.add_evidence(Evidence(id=f"ev-competitor-{row['brand'].lower()}", source=result.source_name, content=f"{row['brand']} {row['model']}：供电 {row['battery']}，价格 {row['price']}。", data_nature='PUBLIC_FIXTURE', confidence='MEDIUM', source_url=row.get('source_url') or result.source_url, source_type=result.source_type, retrieved_at=result.retrieved_at, fallback_reason=result.fallback_reason))
    return rows
