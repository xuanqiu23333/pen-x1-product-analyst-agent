from pydantic import BaseModel, Field
from app.schemas.state import AnalysisState
from app.schemas.models import Opportunity
from app.prompts.opportunity import OPPORTUNITY_PROMPT

class OpportunitySuggestion(BaseModel):
    title: str
    user_problem: str
    validation_needed: list[str] = Field(default_factory=list)

def run_opportunity_analysis(state: AnalysisState, llm_provider=None, mode: str = 'DEMO') -> list[dict]:
    candidates=[]
    competitor_evidence=[item.id for item in state.evidence if item.id.startswith('ev-competitor-')]
    market_evidence=[item.id for item in state.evidence if item.id.startswith('ev-market-')]
    for point in state.voc.get('pain_points', []):
        aspect=point.get('aspect')
        if aspect != 'battery':
            continue
        voc_evidence=point.get('evidence_review_ids', [])
        fact=state.fact_by_id('battery_configurations')
        fact_ids=['battery_configurations'] if fact else []
        complete=bool(voc_evidence and competitor_evidence and market_evidence and fact_ids)
        title='多电池供电灵活性候选机会'
        user_problem=point.get('pain_point','用户需要更灵活的供电选择。')
        validations=['验证各电池配置的实际输出与续航。','验证用户对多电池价值的理解。']
        if mode.upper() == 'REAL' and llm_provider is not None:
            try:
                suggestion=OpportunitySuggestion.model_validate(llm_provider.complete_json(OPPORTUNITY_PROMPT, {'pain_point':user_problem,'voc_evidence':voc_evidence,'competitor_evidence':competitor_evidence,'market_evidence':market_evidence,'product_fact_ids':fact_ids}))
                title,user_problem,validations=suggestion.title,suggestion.user_problem,suggestion.validation_needed or validations
            except Exception:
                pass
        candidates.append(Opportunity(id=f'opp-{aspect}-flexibility', title=title, user_problem=user_problem, voc_evidence=voc_evidence, competitor_gap=competitor_evidence, competitor_evidence=competitor_evidence, product_fact_ids=fact_ids, product_capability='由产品 Fact battery_configurations 解析', market_evidence=market_evidence, confidence='MEDIUM' if complete else 'LOW', status='INFERRED' if complete else 'NEED_VERIFY', validation_needed=validations).model_dump())
    return candidates
