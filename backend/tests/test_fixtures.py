from pathlib import Path

from app.services.data_loader import load_project_facts


DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


def test_pen_x1_fixture_contains_only_supplied_product_facts():
    facts = load_project_facts(DATA_ROOT)

    assert facts["target_price_usd"].value == 34.95
    assert facts["battery_configurations"].value == ["14500", "AA", "AAA", "2AA", "2AAA"]
    assert "max_lumen" not in facts
