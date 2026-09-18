from app.schemas.state import AnalysisState
class DecisionEngine:
    def evaluate(self,state: AnalysisState)->dict:
        sources=state.market.get('research',{}).get('sources',[]) if state.market else []
        has_market=bool(sources); sample_only=has_market and all(item.get('status') in {'PUBLIC_FIXTURE','SAMPLE'} for item in sources)
        real_voc_incomplete = state.project.get('mode') == 'REAL_MODE' and state.voc.get('status') in {'NEED_DATA', 'NEED_LLM'}
        market_status='PENDING' if real_voc_incomplete else 'PARTIAL' if sample_only else ('PASS' if has_market and state.voc.get('review_count',0) else 'PENDING')
        complete_opportunity=any(item.get('status')=='INFERRED' and item.get('voc_evidence') and item.get('competitor_evidence') and item.get('market_evidence') and item.get('product_fact_ids') for item in state.opportunities)
        technical_open=any(item.get('status')=='NEED_VERIFY' and item.get('severity',0)>=4 for item in state.technical_risks)
        manufacturing_open=any(item.get('status')=='NEED_VERIFY' for item in state.lifecycle_risks)
        costs=state.profit_analysis.get('cost_status',{}) if state.profit_analysis else {}; financial_open=any(value=='UNKNOWN' for value in costs.values())
        live_amazon=state.project.get('data_provider_status',{}).get('Amazon SP-API',{}).get('status')=='LIVE'
        market_reason=('真实评论 VOC 尚未完成；不能用示例评论替代。' if real_voc_incomplete else
                       '已有 Amazon SP-API 竞品与聚合反馈，但市场样本仍为演示数据，需补充真实市场覆盖。' if live_amazon and sample_only else
                       '当前市场与用户之声数据为演示数据，流程已验证但真实数据量不足。' if sample_only else '缺少市场或用户之声数据。')
        gates=[{'name':'市场关卡','status':market_status,'reason':market_reason,'evidence_quality':'MIXED_LIVE_AND_FIXTURE' if live_amazon else 'FIXTURE_ONLY'}, {'name':'产品关卡','status':'PARTIAL' if complete_opportunity else 'PENDING','reason':'候选机会是否完整绑定四类证据。'}, {'name':'技术关卡','status':'PENDING' if technical_open else 'PASS','reason':'高严重度待验证技术风险阻止通过。' if technical_open else '没有未缓解的高严重度待验证风险。'}, {'name':'量产 / 上市关卡','status':'PENDING' if manufacturing_open else 'PASS','reason':'生命周期验证状态。'}, {'name':'财务关卡','status':'PENDING' if financial_open else 'PASS','reason':'关键运营成本完整性。'}]
        no_go=any(item.get('severity',0)>=5 and item.get('status')=='NEED_VERIFY' and not item.get('mitigation') for item in state.technical_risks+state.lifecycle_risks)
        decision='NO_GO' if no_go else ('CONDITIONAL_GO' if any(gate['status'] in {'PENDING','PARTIAL'} for gate in gates) else 'GO')
        return {'decision':decision,'gates':gates}
