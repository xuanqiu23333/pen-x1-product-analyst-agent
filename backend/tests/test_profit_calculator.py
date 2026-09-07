from app.services.profit_calculator import calculate_contribution_margin


def test_contribution_margin_uses_python_cost_inputs():
    result = calculate_contribution_margin(price_usd=34.95, bom_rmb=48.6, usd_rmb_rate=7.2)
    assert result.revenue_usd == 34.95
    assert result.bom_usd == 6.75
