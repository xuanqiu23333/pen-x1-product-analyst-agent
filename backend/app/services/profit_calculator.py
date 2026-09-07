from app.schemas.models import ProfitCell


def calculate_contribution_margin(price_usd: float, bom_rmb: float, usd_rmb_rate: float, return_rate: float = 0.0, amazon_fee_rate: float | None = None, fba_usd: float | None = None, freight_usd: float | None = None, advertising_usd: float | None = None) -> ProfitCell:
    bom_usd = round(bom_rmb / usd_rmb_rate, 2)
    amazon_fee = round(price_usd * amazon_fee_rate, 2) if amazon_fee_rate is not None else None
    return_cost = round(price_usd * return_rate, 2)
    known_costs = bom_usd + return_cost + sum(value or 0 for value in [amazon_fee, fba_usd, freight_usd, advertising_usd])
    return ProfitCell(price_usd=price_usd, return_rate=return_rate, revenue_usd=price_usd, bom_usd=bom_usd, amazon_fee_usd=amazon_fee, fba_usd=fba_usd, freight_usd=freight_usd, advertising_usd=advertising_usd, return_cost_usd=return_cost, contribution_margin_usd=round(price_usd-known_costs, 2))


def calculate_profit_matrix(bom_rmb: float, usd_rmb_rate: float = 7.2) -> list[ProfitCell]:
    return [calculate_contribution_margin(price, bom_rmb, usd_rmb_rate, rate) for price in [29.95, 32.95, 34.95, 36.95, 39.95] for rate in [0.03, 0.05, 0.08, 0.10, 0.15]]
