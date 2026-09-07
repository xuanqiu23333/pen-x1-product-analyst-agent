from pathlib import Path
from app.data_providers.fixture_provider import FixtureProvider

DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'

def test_fixture_provider_returns_traceable_market_data_without_network():
    result = FixtureProvider(DATA_ROOT).get_market_data()
    assert result.status == 'READY'
    assert result.source_type == 'FIXTURE'
    assert result.retrieved_at is not None
    assert result.data
