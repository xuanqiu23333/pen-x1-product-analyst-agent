from collections import Counter, defaultdict
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.state import AnalysisState
from app.schemas.models import Evidence, PainPoint
from app.services.data_loader import load_reviews
from app.data_providers.review_csv_provider import ReviewCsvProvider
from app.prompts.voc import REAL_VOC_PROMPT
from app.llm.mock_provider import MockLLMProvider

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

class RealSemanticAspect(BaseModel):
    aspect: Literal['brightness', 'runtime', 'battery', 'charging', 'switch', 'modes',
                    'clip', 'size', 'weight', 'durability', 'waterproof', 'heat', 'beam', 'price', 'other']
    sentiment: Literal['positive', 'negative', 'neutral']
    pain_point: str = Field(min_length=1)
    severity: Literal['low', 'medium', 'high']

class RealSemanticReview(BaseModel):
    review_id: str
    sentiment: Literal['positive', 'negative', 'neutral']
    usage_scenario: str | None
    purchase_reason: str | None
    aspects: list[RealSemanticAspect]

class RealSemanticBatch(BaseModel):
    items: list[RealSemanticReview]

def _feedback_rows(state: AnalysisState, amazon_feedback: list[dict] | None) -> list[dict]:
    feedback = []
    for item in amazon_feedback or []:
        evidence = next((row for row in state.evidence
                         if row.id.startswith(f"ev-amazon-feedback-{item['asin']}-{item['sentiment']}-")
                         and item['topic'] in row.content), None)
        feedback.append({'asin': item['asin'], 'topic': item['topic'], 'sentiment': item['sentiment'],
                         'mentions': item.get('mentions'), 'star_rating_impact': item.get('star_rating_impact'),
                         'trend': item.get('trend', []), 'evidence_id': evidence.id if evidence else None})
    return feedback

def _real_voc(state: AnalysisState, reviews: list[dict], llm_provider, amazon_feedback: list[dict] | None) -> dict:
    count = len(reviews)
    coverage = 'NEED_DATA' if not count else 'LOW_COVERAGE' if count < 50 else 'PARTIAL' if count < 200 else 'SUFFICIENT_FOR_DEMO'
    feedback = _feedback_rows(state, amazon_feedback)
    result = {'status': 'NEED_DATA', 'review_count': count, 'coverage_level': coverage,
              'classification_source': 'UNAVAILABLE', 'pain_points': [],
              'amazon_feedback_topics': len(feedback),
              'amazon_feedback_mentions': sum(item.get('mentions') or 0 for item in feedback),
              'amazon_feedback': feedback, 'sources': [{'source': 'CSV 导入的真实评论（未经平台核验）',
                                                'data_nature': 'IMPORTED_DATA'}] +
              ([{'source': 'Amazon Customer Feedback API', 'data_nature': 'PUBLIC_DATA'}] if feedback else []),
              'data_notice': '无有效真实导入评论，VOC 需要数据；未使用示例评论。'}
    if not reviews:
        return result
    for row in reviews:
        state.add_evidence(Evidence(id=f"ev-review-{row['review_id']}",
                                    source='CSV 导入的真实评论（未经 Amazon 平台核验）',
                                    content=row['review_text'], data_nature='IMPORTED_DATA',
                                    confidence='MEDIUM', source_type='IMPORTED_REAL',
                                    source_url=row['source_url'], retrieved_at=row['collected_at'],
                                    collected_at=row['collected_at'], external_review_id=row['external_review_id'],
                                    product_name=row['product_name'], asin=row['asin'], rating=row['rating'],
                                    review_date=row['review_date'], helpful_votes=row['helpful_votes'],
                                    verified_purchase=bool(row['verified_purchase'])))
    result['status'] = 'NEED_LLM'
    result['data_notice'] = '真实评论已导入，但 DeepSeek 结构化 VOC 尚未完成；未使用示例或规则分类。'
    if llm_provider is None or isinstance(llm_provider, MockLLMProvider):
        return result
    semantic_items: list[RealSemanticReview] = []
    try:
        for start in range(0, count, 25):
            batch = reviews[start:start + 25]
            payload = {'reviews': [{'review_id': row['review_id'], 'rating': row['rating'],
                                    'title': row['title'], 'review_text': row['review_text']}
                                   for row in batch]}
            classified = RealSemanticBatch.model_validate(llm_provider.complete_json(REAL_VOC_PROMPT, payload)).items
            if len(classified) != len(batch) or {item.review_id for item in classified} != {row['review_id'] for row in batch}:
                return result
            semantic_items.extend(classified)
    except Exception:
        return result
    review_index = {row['review_id']: row for row in reviews}
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    semantic_index = {item.review_id: item for item in semantic_items}
    for item in semantic_items:
        for aspect in item.aspects:
            if aspect.sentiment == 'negative' and aspect.pain_point.strip():
                grouped[(aspect.aspect, aspect.pain_point.strip(), aspect.severity)].append(item.review_id)
    points = []
    for (aspect, pain_point, severity), ids in grouped.items():
        unique_ids = list(dict.fromkeys(ids))
        rows = [review_index[review_id] for review_id in unique_ids]
        points.append(PainPoint(pain_point=pain_point, aspect=aspect, mentions=len(rows),
                                frequency=round(len(rows) / count, 4), severity=severity.upper(),
                                products=sorted({row['product_name'] for row in rows}),
                                evidence_review_ids=[f'ev-review-{review_id}' for review_id in unique_ids],
                                confidence='MEDIUM', avg_rating=round(sum(row['rating'] for row in rows) / len(rows), 2),
                                product_distribution=dict(Counter(row['product_name'] for row in rows)),
                                usage_scenarios=sorted({semantic_index[review_id].usage_scenario for review_id in unique_ids
                                                        if semantic_index[review_id].usage_scenario}),
                                purchase_reasons=sorted({semantic_index[review_id].purchase_reason for review_id in unique_ids
                                                         if semantic_index[review_id].purchase_reason})).model_dump())
    result.update(status='COMPLETED', classification_source='LLM_STRUCTURED',
                  pain_points=sorted(points, key=lambda item: item['mentions'], reverse=True),
                  data_notice='VOC 使用已导入真实评论和 DeepSeek 结构化分类；导入来源未经 Amazon 平台独立核验。')
    return result

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

def run_voc_analysis(state: AnalysisState, data_root, llm_provider=None, mode: str = 'DEMO', review_provider=None, amazon_feedback: list[dict] | None = None) -> dict:
    if mode.upper() == 'REAL':
        source = (review_provider or ReviewCsvProvider(data_root, mode='REAL')).get_reviews()
        reviews = (source.data or []) if source.source_type == 'IMPORTED_REAL' else []
        return _real_voc(state, reviews, llm_provider, amazon_feedback)
    reviews = review_provider.get_reviews().data if review_provider else load_reviews(data_root)
    classification_source='RULE_FALLBACK'
    semantic_items = _fallback_classifications(reviews)
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
    feedback = _feedback_rows(state, amazon_feedback)
    return {'review_count':len(reviews), 'amazon_feedback_topics':len(feedback),
        'amazon_feedback_mentions':sum(item['mentions'] or 0 for item in feedback),
        'amazon_feedback':feedback,
        'data_notice':'CSV 原始评论与 Amazon 官方聚合主题分别统计；官方接口不提供评论全集。' if feedback else '示例评论数据；不是实时亚马逊评论数据。',
        'classification_source':classification_source, 'pain_points':sorted(pain_points,key=lambda item:item['mentions'],reverse=True),
        'sources':[{'source':'评论 CSV 导入','data_nature':'SAMPLE'}]+([{'source':'Amazon Customer Feedback API','data_nature':'PUBLIC_DATA'}] if feedback else [])}
