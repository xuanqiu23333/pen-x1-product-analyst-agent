from collections import defaultdict
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.state import AnalysisState
from app.schemas.models import Evidence, PainPoint
from app.services.data_loader import load_reviews
from app.prompts.voc import VOC_PROMPT

ASPECTS = {"battery": ["battery", "batteries"], "clip": ["clip"], "runtime": ["runtime"], "brightness": ["brightness"]}
ALLOWED_ASPECTS = set('brightness runtime battery charging switch modes clip size weight durability waterproof heat beam price other'.split())

class SemanticAspect(BaseModel):
    aspect: str
    sentiment: Literal['positive', 'negative', 'neutral']
    pain_point: str
    severity: Literal['low', 'medium', 'high']

class SemanticReview(BaseModel):
    review_id: str
    sentiment: Literal['positive', 'negative', 'neutral']
    aspects: list[SemanticAspect] = Field(default_factory=list)

class SemanticBatch(BaseModel):
    items: list[SemanticReview]

def _fallback_classifications(reviews: list[dict]) -> list[SemanticReview]:
    items=[]
    for review in reviews:
        text=f"{review['title']} {review['review_text']}".lower()
        aspects=[]
        for aspect, words in ASPECTS.items():
            if any(word in text for word in words):
                aspects.append(SemanticAspect(aspect=aspect, sentiment='negative' if int(review['rating']) <= 3 else 'positive', pain_point={'battery':'电池适配与可获得性','clip':'口袋夹固定性','runtime':'续航信息表达','brightness':'亮度预期'}[aspect], severity='high' if aspect == 'clip' else 'medium'))
        items.append(SemanticReview(review_id=review['review_id'], sentiment='negative' if int(review['rating']) <= 3 else 'positive', aspects=aspects))
    return items

def run_voc_analysis(state: AnalysisState, data_root, llm_provider=None, mode: str = 'DEMO', review_provider=None) -> dict:
    reviews = review_provider.get_reviews().data if review_provider else load_reviews(data_root)
    classification_source='RULE_FALLBACK'
    semantic_items=None
    if mode.upper() == 'REAL' and llm_provider is not None:
        try:
            payload={'reviews':[{'review_id':r['review_id'],'rating':r['rating'],'title':r['title'],'review_text':r['review_text']} for r in reviews]}
            semantic_items=SemanticBatch.model_validate(llm_provider.complete_json(VOC_PROMPT, payload)).items
            classification_source='LLM_STRUCTURED'
        except Exception:
            semantic_items=None
    semantic_items = semantic_items or _fallback_classifications(reviews)
    review_index={review['review_id']:review for review in reviews}
    grouped=defaultdict(list)
    for item in semantic_items:
        for aspect in item.aspects:
            if aspect.aspect in ALLOWED_ASPECTS:
                grouped[(aspect.aspect, aspect.pain_point, aspect.severity)].append(item.review_id)
    pain_points=[]
    for (aspect, pain_point, severity), review_ids in grouped.items():
        unique_ids=list(dict.fromkeys(review_ids)); rows=[review_index[item] for item in unique_ids if item in review_index]
        for row in rows:
            state.add_evidence(Evidence(id=f"ev-review-{row['review_id']}", source=row['source'], content=row['review_text'], data_nature='SAMPLE', confidence='LOW'))
        pain_points.append(PainPoint(pain_point=pain_point, aspect=aspect, mentions=len(unique_ids), frequency=round(len(unique_ids)/len(reviews),2) if reviews else 0, severity=severity.upper(), products=sorted({row['product'] for row in rows}), evidence_review_ids=[f"ev-review-{item}" for item in unique_ids], confidence='LOW' if classification_source != 'LLM_STRUCTURED' else 'MEDIUM').model_dump())
    return {'review_count':len(reviews), 'data_notice':'示例评论数据；不是实时亚马逊评论数据。', 'classification_source':classification_source, 'pain_points':sorted(pain_points,key=lambda item:item['mentions'],reverse=True), 'sources':[{'source':'评论 CSV 导入','data_nature':'SAMPLE'}]}
