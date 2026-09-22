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
    real = mode.upper() == 'REAL'
    points = state.voc.get('canonical_pain_points', []) if real else state.voc.get('pain_points', [])
    for index, point in enumerate(points, 1):
        aspect=point.get('aspect')
        if not real and aspect != 'battery':
            continue
        amazon_evidence=[item['evidence_id'] for item in state.voc.get('amazon_feedback',[])
                         if item.get('sentiment')=='negative' and item.get('evidence_id')
                         and (aspect.lower() in item.get('topic','').lower())]
        point_evidence = point.get('evidence_ids', point.get('evidence_review_ids', []))
        voc_evidence=list(dict.fromkeys(point_evidence+amazon_evidence))
        fact_key = ('battery_configurations' if aspect in {'battery', 'charging', 'runtime'} else
                    'target_price_usd' if aspect in {'brightness', 'price'} else None)
        fact=state.fact_by_id(fact_key) if fact_key else None
        fact_ids=[fact_key] if fact else []
        complete=bool(voc_evidence and competitor_evidence and market_evidence and fact_ids)
        canonical_name = point.get('canonical_pain_point') or point.get('pain_point', aspect)
        title=('多电池方案与续航验证机会' if aspect in {'battery', 'charging', 'runtime'} else
               f"{canonical_name}的产品验证机会")
        user_problem=canonical_name or '用户需要更灵活的供电选择。'
        validations=(['验证各电池配置的实际输出与续航。','验证用户对多电池价值的理解。']
                     if aspect in {'battery', 'charging'} else
                     [f'验证“{user_problem}”是否能通过 PEN-X1 设计解决。', '验证改进对可靠性、成本和用户体验的影响。'])
        if not real and llm_provider is not None:
            try:
                suggestion=OpportunitySuggestion.model_validate(llm_provider.complete_json(OPPORTUNITY_PROMPT, {'pain_point':user_problem,'voc_evidence':voc_evidence,'competitor_evidence':competitor_evidence,'market_evidence':market_evidence,'product_fact_ids':fact_ids}))
                title,user_problem,validations=suggestion.title,suggestion.user_problem,suggestion.validation_needed or validations
            except Exception:
                pass
        supporting_ids=list(dict.fromkeys(point_evidence))
        cross_product = bool(point.get('cross_product_support')) or len(point.get('products', [])) >= 2
        product_rate = float(point.get('product_mention_rate', 0) or 0)
        corpus_rate = float(point.get(
            'corpus_mention_rate', point.get('mention_rate', point.get('frequency', 0))) or 0)
        confidence='MEDIUM' if len(supporting_ids) >= 2 else 'LOW'
        if fact_key == 'battery_configurations':
            capability='多电池兼容设计可能提供解决方向；实际输出与续航 NEED_VERIFY'
        elif fact_key == 'target_price_usd':
            capability=(f'目标价格 ${fact.value} 可用于价值定位；实际亮度与用户价值 NEED_VERIFY'
                        if fact else 'UNKNOWN / NEED_VERIFY')
        else:
            capability='UNKNOWN / NEED_VERIFY'
        candidates.append(Opportunity(
            id=f'opp-{aspect}-{index}', title=title, opportunity=title, user_problem=user_problem,
            voc_evidence=voc_evidence, competitor_gap=competitor_evidence,
            competitor_evidence=competitor_evidence, product_fact_ids=fact_ids,
            product_capability=capability, market_evidence=market_evidence,
            confidence=confidence, status='INFERRED' if complete else 'NEED_VERIFY',
            validation_needed=validations,
            source_pain_points=point.get('raw_pain_points', [user_problem]),
            supporting_reviews=len(supporting_ids), evidence_ids=supporting_ids,
            mention_frequency=product_rate or corpus_rate,
            affected_products=sorted(point.get('products') or point.get('affected_products') or point.get('product_distribution', {}).keys()),
            canonical_pain_points=[canonical_name], cross_product_support=cross_product,
            product_mention_rate=product_rate, corpus_mention_rate=corpus_rate,
            product_distribution=point.get('product_distribution', {}),
        ).model_dump())
    return candidates
