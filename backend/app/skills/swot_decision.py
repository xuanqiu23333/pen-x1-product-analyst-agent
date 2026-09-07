from app.schemas.state import AnalysisState

def run_swot_decision(state: AnalysisState) -> tuple[dict, dict]:
    swot = {"strengths":[{"text":"Five stated battery configurations", "evidence_ids":["battery_configurations"]}], "weaknesses":[{"text":"No supplied performance, thermal or certification parameters", "evidence_ids":[]}], "opportunities":[{"text":"Supply flexibility is an inferred candidate opportunity", "evidence_ids":["opp-power-flexibility"]}], "threats":[{"text":"Battery identification and mechanical compatibility remain unverified", "evidence_ids":["battery-identification", "mechanical-tolerance"]}]}
    gates = [{"name":"市场关卡","status":"通过","reason":"已具备演示市场调研和示例用户之声数据。"}, {"name":"产品关卡","status":"待验证","reason":"价值主张仍需用户理解度验证。"}, {"name":"技术关卡","status":"待验证","reason":"五电池、BOOST、温升和机械测试尚未完成。"}, {"name":"量产 / 上市关卡","status":"待验证","reason":"EOL、合规与页面控制仍需验证。"}, {"name":"财务关卡","status":"待验证","reason":"FBA、佣金、运费和广告成本仍未知。"}]
    decision = {"decision":"CONDITIONAL_GO", "rationale":["市场信号目前仅来自演示数据和示例数据。", "技术验证仍然必需。", "财务模型缺少运营成本输入。"], "gates":gates}
    return swot, decision

