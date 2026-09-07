from pydantic import BaseModel, Field
from app.schemas.state import AnalysisState
from app.services.decision_engine import DecisionEngine
class DecisionNarrative(BaseModel): rationale: list[str]=Field(default_factory=list)
def run_swot_decision(state: AnalysisState,llm_provider=None,mode: str='DEMO')->tuple[dict,dict]:
    rationale=['决策由市场、产品、技术、量产/上市和财务关卡推导。']
    if mode.upper()=='REAL' and llm_provider is not None:
        try:
            llm=DecisionNarrative.model_validate(llm_provider.complete_json('仅返回 JSON：{"rationale":["基于输入证据的谨慎决策理由"]}。不得编造新事实。',{'opportunities':state.opportunities,'risks':state.technical_risks+state.lifecycle_risks})); rationale=llm.rationale or rationale; state.project.setdefault('llm_skill_calls',[]).append('优势劣势机会威胁与决策')
        except Exception as error: state.project.setdefault('warnings',[]).append(f'决策的模型补充不可用：{error}')
    swot={'strengths':[{'text':'五种已声明电池配置','evidence_ids':['battery_configurations']}],'weaknesses':[{'text':'未提供性能、温升或认证参数','evidence_ids':[]}],'opportunities':[{'text':item['title'],'evidence_ids':item.get('voc_evidence',[])+item.get('competitor_evidence',[])} for item in state.opportunities],'threats':[{'text':'电池识别与机械兼容性未验证','evidence_ids':['battery-identification','mechanical-tolerance']}]}
    decision=DecisionEngine().evaluate(state); decision['rationale']=rationale
    return swot,decision
