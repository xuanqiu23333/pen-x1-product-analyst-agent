from app.schemas.state import AnalysisState
from app.schemas.models import Evidence
from app.data_providers.fixture_provider import FixtureProvider

def run_market_research(state: AnalysisState, data_root, market_provider=None) -> dict:
    result = market_provider.get_market_data() if market_provider else FixtureProvider(data_root).get_market_data()
    rows = result.data or []
    for index, row in enumerate(rows, 1):
        state.add_evidence(Evidence(id=f'ev-market-{index}', source=result.source_name, content=f"{row['keyword']}：{row['price_range']}；样本量 {row['product_count_sample']}。", data_nature='PUBLIC_FIXTURE', confidence='MEDIUM', source_url=result.source_url, source_type=result.source_type, retrieved_at=result.retrieved_at, fallback_reason=result.fallback_reason))
    return {'price_segments':[row['price_range'] for row in rows], 'common_features':sorted({feature for row in rows for feature in row['main_features']}), 'battery_patterns':[row['battery_type'] for row in rows], 'customer_scenarios':['日常随身携带','家庭应急','轻度户外'], 'market_observations':['数据来源状态已记录；演示数据不等同于实时亚马逊数据。'], 'sources':rows, 'provider':result.__dict__}
