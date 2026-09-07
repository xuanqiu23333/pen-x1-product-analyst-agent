from app.schemas.state import AnalysisState
class DecisionEngine:
    def evaluate(self,state: AnalysisState)->dict:
        sources=state.market.get('research',{}).get('sources',[]) if state.market else []
        has_market=bool(sources); sample_only=has_market and all(item.get('status') in {'PUBLIC_FIXTURE','SAMPLE'} for item in sources)
        market_status='PARTIAL' if sample_only else ('PASS' if has_market and state.voc.get('review_count',0) else 'PENDING')
        complete_opportunity=any(item.get('status')=='INFERRED' and item.get('voc_evidence') and item.get('competitor_evidence') and item.get('market_evidence') and item.get('product_fact_ids') for item in state.opportunities)
        technical_open=any(item.get('status')=='NEED_VERIFY' and item.get('severity',0)>=4 for item in state.technical_risks)
        manufacturing_open=any(item.get('status')=='NEED_VERIFY' for item in state.lifecycle_risks)
        costs=state.profit_analysis.get('cost_status',{}) if state.profit_analysis else {}; financial_open=any(value=='UNKNOWN' for value in costs.values())
        gates=[{'name':'市场关卡','status':market_status,'reason':'当前市场与用户之声数据为演示数据，流程已验证但真实数据量不足。' if sample_only else '缺少市场或用户之声数据。'}, {'name':'产品关卡','status':'PARTIAL' if complete_opportunity else 'PENDING','reason':'候选机会是否完整绑定四类证据。'}, {'name':'技术关卡','status':'PENDING' if technical_open else 'PASS','reason':'高严重度待验证技术风险阻止通过。' if technical_open else '没有未缓解的高严重度待验证风险。'}, {'name':'量产 / 上市关卡','status':'PENDING' if manufacturing_open else 'PASS','reason':'生命周期验证状态。'}, {'name':'财务关卡','status':'PENDING' if financial_open else 'PASS','reason':'关键运营成本完整性。'}]
        no_go=any(item.get('severity',0)>=5 and item.get('status')=='NEED_VERIFY' and not item.get('mitigation') for item in state.technical_risks+state.lifecycle_risks)
        decision='NO_GO' if no_go else ('CONDITIONAL_GO' if any(gate['status'] in {'PENDING','PARTIAL'} for gate in gates) else 'GO')
        return {'decision':decision,'gates':gates}
