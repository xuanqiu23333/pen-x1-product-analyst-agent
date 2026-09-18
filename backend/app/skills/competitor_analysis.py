from app.schemas.state import AnalysisState
from app.schemas.models import Evidence
from app.data_providers.fixture_provider import FixtureProvider

def run_competitor_analysis(state: AnalysisState, data_root, competitor_provider=None) -> list[dict]:
    result = competitor_provider.get_competitor_data() if competitor_provider else FixtureProvider(data_root).get_competitor_data()
    rows = result.data or []
    for row in rows:
        source_type = row.get('source_type') or result.source_type
        nature = row.get('data_nature') or ('PUBLIC_DATA' if row.get('status') == 'LIVE' else 'PUBLIC_FIXTURE')
        battery = row.get('battery') or '未知'
        price = row.get('price') if row.get('price') is not None else '未知'
        state.add_evidence(Evidence(id=f"ev-competitor-{row['brand'].lower()}", source=source_type, source_name=result.source_name, content=f"{row['brand']} {row['model']}：供电 {battery}，价格 {price}。", data_nature=nature, confidence='HIGH' if nature == 'PUBLIC_DATA' else 'MEDIUM', source_url=row.get('source_url') or result.source_url, source_type=source_type, retrieved_at=row.get('retrieved_at') or result.retrieved_at, fallback_reason=result.fallback_reason if nature == 'PUBLIC_FIXTURE' else None))
    return rows
