from collections import Counter, defaultdict
import json
import re
from typing import Literal
from pydantic import BaseModel, Field, ValidationError, model_validator
from app.schemas.state import AnalysisState
from app.schemas.models import Evidence, PainPoint
from app.services.data_loader import load_reviews
from app.services.review_cleaning import review_coverage_level
from app.services.pain_point_canonicalizer import canonicalize_pain_points
from app.data_providers.review_csv_provider import ReviewCsvProvider
from app.prompts.voc import REAL_VOC_PROMPT
from app.llm.deepseek_provider import DeepSeekError
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
    pain_point: str | None = None
    severity: Literal['low', 'medium', 'high']

    @model_validator(mode='after')
    def negative_requires_pain_point(self):
        if self.sentiment == 'negative' and not (self.pain_point or '').strip():
            raise ValueError('negative aspect requires a non-empty pain_point')
        return self

class RealSemanticReview(BaseModel):
    review_id: str
    sentiment: Literal['positive', 'negative', 'neutral']
    usage_scenario: str | None = None
    purchase_reason: str | None = None
    aspects: list[RealSemanticAspect] = Field(default_factory=list)

class RealSemanticBatch(BaseModel):
    items: list[RealSemanticReview]


def _empty_llm_diagnostic() -> dict:
    return {
        'failure_stage': None, 'exception_type': None, 'error_code': None,
        'safe_message': None, 'batch_index': None, 'expected_count': None,
        'actual_count': None, 'missing_review_ids': [], 'extra_review_ids': [],
        'duplicate_review_ids': [], 'validation_errors': [],
    }


def _safe_message(error: Exception) -> str:
    message = str(error)[:1000]
    message = re.sub(r'(?i)bearer\s+\S+', 'Bearer [REDACTED]', message)
    return re.sub(
        r'(?i)(authorization|api[_ -]?(?:token|key))\s*[:=]\s*\S+',
        r'\1=[REDACTED]', message,
    )


def _pydantic_errors(error: ValidationError) -> list[dict]:
    return [
        {'location': '.'.join(str(part) for part in item['loc']),
         'type': item['type'], 'message': item['msg']}
        for item in error.errors(include_url=False, include_input=False)
    ]

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

def _real_voc(state: AnalysisState, reviews: list[dict], llm_provider,
              amazon_feedback: list[dict] | None, product_aliases: dict[str, str] | None = None) -> dict:
    count = len(reviews)
    product_aliases = product_aliases or {}
    product_label = lambda row: product_aliases.get(str(row.get('asin') or '').upper(), row['product_name'])
    source_counts = dict(Counter(row.get('source_type', 'UNKNOWN') for row in reviews))
    coverage = review_coverage_level(count)
    feedback = _feedback_rows(state, amazon_feedback)
    product_counts = dict(sorted(Counter(product_label(row) for row in reviews).items()))
    rating_distribution: dict[str, dict[str, int]] = {}
    verified_purchase_ratio: dict[str, float] = {}
    helpful_vote_signals: dict[str, dict[str, int]] = {}
    for product in product_counts:
        product_rows = [row for row in reviews if product_label(row) == product]
        rating_distribution[product] = dict(sorted(Counter(
            str(int(row['rating'])) if float(row['rating']).is_integer() else str(row['rating'])
            for row in product_rows).items()))
        verified_purchase_ratio[product] = round(
            sum(bool(row.get('verified_purchase')) for row in product_rows) / len(product_rows), 4)
        helpful_vote_signals[product] = {
            'reviews_with_helpful_votes': sum(int(row.get('helpful_votes') or 0) > 0 for row in product_rows),
            'helpful_votes': sum(int(row.get('helpful_votes') or 0) for row in product_rows),
        }
    result = {'status': 'NEED_DATA', 'review_count': count, 'coverage_level': coverage,
              'classification_source': 'UNAVAILABLE', 'pain_points': [], 'canonical_pain_points': [],
              'positive_feedback': [], 'negative_feedback': [], 'recurring_complaints': [],
              'usage_scenarios': [], 'purchase_drivers': [], 'product_insights': {},
              'product_review_counts': product_counts, 'products_analyzed': len(product_counts),
              'rating_distribution': rating_distribution,
              'verified_purchase_ratio': verified_purchase_ratio,
              'helpful_vote_signals': helpful_vote_signals,
              'llm_diagnostic': _empty_llm_diagnostic(),
              'successful_batches': [], 'failed_batch': None,
              'amazon_feedback_topics': len(feedback),
              'amazon_feedback_mentions': sum(item.get('mentions') or 0 for item in feedback),
              'amazon_feedback': feedback, 'source_counts': source_counts,
              'sources': ([{'source': 'CSV 导入的真实评论（未经平台核验）', 'data_nature': 'IMPORTED_DATA'}]
                          if source_counts.get('IMPORTED_REAL') else []) +
              ([{'source': 'Bright Data API 获取的真实 Amazon 评论', 'data_nature': 'IMPORTED_DATA'}]
                if source_counts.get('BRIGHTDATA_REAL') else []) +
              ([{'source': 'Apify API 获取的真实 Amazon 评论', 'data_nature': 'IMPORTED_DATA'}]
               if source_counts.get('APIFY_REAL') else []) +
              ([{'source': 'Amazon Customer Feedback API', 'data_nature': 'PUBLIC_DATA'}] if feedback else []),
              'data_notice': '无有效真实评论，VOC 需要数据；未使用示例评论。'}
    if not reviews:
        return result
    for row in reviews:
        state.add_evidence(Evidence(id=f"ev-review-{row['review_id']}",
                                    source=row.get('source') or '真实评论',
                                    content=row['review_text'], data_nature='IMPORTED_DATA',
                                    confidence='MEDIUM', source_type=row['source_type'],
                                    source_url=row.get('review_url'), review_url=row.get('review_url'),
                                    product_url=row.get('product_url'), retrieved_at=row['collected_at'],
                                    collected_at=row['collected_at'], external_review_id=row['external_review_id'],
                                    product_name=row['product_name'], asin=row['asin'], rating=row['rating'],
                                    review_title=row.get('title'),
                                    review_date=row['review_date'], helpful_votes=row['helpful_votes'],
                                    verified_purchase=bool(row['verified_purchase'])))
    result['status'] = 'NEED_LLM'
    result['data_notice'] = '真实评论已就绪，但 DeepSeek 结构化 VOC 尚未完成；未使用示例或规则分类。'
    if llm_provider is None or isinstance(llm_provider, MockLLMProvider):
        return result
    semantic_items: list[RealSemanticReview] = []
    for batch_index, start in enumerate(range(0, count, 8), 1):
        batch = reviews[start:start + 8]
        expected_ids = [row['review_id'] for row in batch]
        payload = {'reviews': [{'review_id': row['review_id'], 'rating': row['rating'],
                                'title': row['title'], 'review_text': row['review_text']}
                               for row in batch]}
        classified = None
        diagnostic = _empty_llm_diagnostic()
        for _attempt in range(2):
            diagnostic = _empty_llm_diagnostic() | {
                'batch_index': batch_index, 'expected_count': len(batch),
            }
            try:
                raw = llm_provider.complete_json(REAL_VOC_PROMPT, payload)
            except DeepSeekError as error:
                diagnostic.update(
                    failure_stage=error.failure_stage,
                    exception_type=type(error).__name__, error_code=error.error_code,
                    safe_message=error.safe_message,
                )
                continue
            except Exception as error:
                diagnostic.update(
                    failure_stage='UNKNOWN', exception_type=type(error).__name__,
                    safe_message=_safe_message(error),
                )
                continue
            raw_items = raw.get('items', []) if isinstance(raw, dict) else []
            diagnostic['actual_count'] = len(raw_items) if isinstance(raw_items, list) else None
            try:
                classified = RealSemanticBatch.model_validate(raw).items
            except ValidationError as error:
                diagnostic.update(
                    failure_stage='PYDANTIC_VALIDATION', exception_type='ValidationError',
                    safe_message='DeepSeek Structured Output 未通过 Pydantic 校验。',
                    validation_errors=_pydantic_errors(error),
                )
                classified = None
                continue
            returned_ids = [item.review_id for item in classified]
            returned_counts = Counter(returned_ids)
            missing = sorted(set(expected_ids) - set(returned_ids))
            extra = sorted(set(returned_ids) - set(expected_ids))
            duplicates = sorted(review_id for review_id, amount in returned_counts.items() if amount > 1)
            if len(classified) != len(batch) or missing or extra or duplicates:
                diagnostic.update(
                    failure_stage='REVIEW_ID_INTEGRITY', exception_type='ReviewIDIntegrityError',
                    safe_message='DeepSeek 返回的 review_id 与输入批次不一致。',
                    actual_count=len(classified), missing_review_ids=missing,
                    extra_review_ids=extra, duplicate_review_ids=duplicates,
                )
                classified = None
                continue
            diagnostic = _empty_llm_diagnostic()
            break
        if classified is None:
            result['llm_diagnostic'] = diagnostic
            result['failed_batch'] = batch_index
            return result
        semantic_items.extend(classified)
        result['successful_batches'].append(batch_index)
    review_index = {row['review_id']: row for row in reviews}
    evidence_product_map = {
        f"ev-review-{row['review_id']}": product_label(row) for row in reviews
    }
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    semantic_index = {item.review_id: item for item in semantic_items}
    for item in semantic_items:
        for aspect in item.aspects:
            if aspect.sentiment == 'negative' and (aspect.pain_point or '').strip():
                grouped[(aspect.aspect, aspect.pain_point.strip(), aspect.severity)].append(item.review_id)
    points = []
    for (aspect, pain_point, severity), ids in grouped.items():
        unique_ids = list(dict.fromkeys(ids))
        rows = [review_index[review_id] for review_id in unique_ids]
        points.append(PainPoint(pain_point=pain_point, topic=pain_point, aspect=aspect, mentions=len(rows),
                                frequency=round(len(rows) / count, 4), severity=severity.upper(),
                                products=sorted({product_label(row) for row in rows}),
                                evidence_review_ids=[f'ev-review-{review_id}' for review_id in unique_ids],
                                confidence='MEDIUM', avg_rating=round(sum(row['rating'] for row in rows) / len(rows), 2),
                                product_distribution=dict(Counter(product_label(row) for row in rows)),
                                usage_scenarios=sorted({semantic_index[review_id].usage_scenario for review_id in unique_ids
                                                        if semantic_index[review_id].usage_scenario}),
                                purchase_reasons=sorted({semantic_index[review_id].purchase_reason for review_id in unique_ids
                                                         if semantic_index[review_id].purchase_reason}),
                                sample_size=count, mention_count=len(rows),
                                mention_rate=round(len(rows) / count, 4),
                                affected_products=sorted({product_label(row) for row in rows})).model_dump())
    positive_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    usage_groups: dict[str, list[str]] = defaultdict(list)
    purchase_groups: dict[str, list[str]] = defaultdict(list)
    for item in semantic_items:
        if item.usage_scenario:
            usage_groups[item.usage_scenario.strip()].append(item.review_id)
        if item.purchase_reason:
            purchase_groups[item.purchase_reason.strip()].append(item.review_id)
        for aspect in item.aspects:
            if aspect.sentiment == 'positive':
                positive_groups[(aspect.aspect, (aspect.pain_point or aspect.aspect).strip())].append(item.review_id)

    def conclusions(groups: dict, label_names: tuple[str, ...], sample_size: int = count) -> list[dict]:
        rows_out = []
        for label, review_ids in groups.items():
            unique_ids = list(dict.fromkeys(review_ids))
            related = [review_index[review_id] for review_id in unique_ids]
            item = {
                'sample_size': sample_size,
                'mention_count': len(unique_ids),
                'mention_rate': round(len(unique_ids) / sample_size, 4) if sample_size else 0,
                'affected_products': sorted({product_label(row) for row in related}),
                'evidence_ids': [f'ev-review-{review_id}' for review_id in unique_ids],
            }
            values = label if isinstance(label, tuple) else (label,)
            item.update(dict(zip(label_names, values)))
            item['topic'] = str(values[-1])
            rows_out.append(item)
        return sorted(rows_out, key=lambda item: item['mention_count'], reverse=True)

    ordered_points = sorted(points, key=lambda item: item['mentions'], reverse=True)
    product_insights = {}
    for product, product_count in product_counts.items():
        product_ids = {row['review_id'] for row in reviews if product_label(row) == product}
        product_negative: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        product_positive: dict[tuple[str, str], list[str]] = defaultdict(list)
        product_usage: dict[str, list[str]] = defaultdict(list)
        product_purchase: dict[str, list[str]] = defaultdict(list)
        for item in semantic_items:
            if item.review_id not in product_ids:
                continue
            if item.usage_scenario:
                product_usage[item.usage_scenario.strip()].append(item.review_id)
            if item.purchase_reason:
                product_purchase[item.purchase_reason.strip()].append(item.review_id)
            for aspect in item.aspects:
                if aspect.sentiment == 'negative' and (aspect.pain_point or '').strip():
                    product_negative[(aspect.aspect, aspect.pain_point.strip(), aspect.severity)].append(item.review_id)
                elif aspect.sentiment == 'positive':
                    product_positive[(aspect.aspect, (aspect.pain_point or aspect.aspect).strip())].append(item.review_id)
        product_points = []
        for (aspect, pain_point, severity), review_ids in product_negative.items():
            unique_ids = list(dict.fromkeys(review_ids))
            product_points.append({
                'pain_point': pain_point, 'topic': pain_point, 'aspect': aspect, 'severity': severity.upper(),
                'sample_size': product_count, 'mention_count': len(unique_ids),
                'mention_rate': round(len(unique_ids) / product_count, 4),
                'affected_products': [product],
                'evidence_review_ids': [f'ev-review-{review_id}' for review_id in unique_ids],
            })
        product_points.sort(key=lambda item: item['mention_count'], reverse=True)
        product_insights[product] = {
            'review_count': product_count,
            'rating_distribution': rating_distribution.get(product, {}),
            'verified_purchase_ratio': verified_purchase_ratio.get(product, 0),
            'helpful_vote_signals': helpful_vote_signals.get(product, {}),
            'pain_points': product_points,
            'canonical_pain_points': canonicalize_pain_points(
                product_points, product_count, {product: product_count}, evidence_product_map),
            'negative_feedback': product_points,
            'recurring_complaints': [item for item in product_points if item['mention_count'] >= 2],
            'positive_feedback': conclusions(product_positive, ('aspect', 'signal'), product_count),
            'usage_scenarios': conclusions(product_usage, ('scenario',), product_count),
            'purchase_drivers': conclusions(product_purchase, ('driver',), product_count),
        }
    result.update(status='COMPLETED', classification_source='LLM_STRUCTURED',
                  pain_points=ordered_points, negative_feedback=ordered_points,
                  canonical_pain_points=canonicalize_pain_points(
                      ordered_points, count, product_counts, evidence_product_map),
                  recurring_complaints=[item for item in ordered_points if item['mention_count'] >= 2],
                  positive_feedback=conclusions(positive_groups, ('aspect', 'signal')),
                  usage_scenarios=conclusions(usage_groups, ('scenario',)),
                  purchase_drivers=conclusions(purchase_groups, ('driver',)),
                  product_insights=product_insights,
                  data_notice=('当前结论基于已获取的真实 Amazon 评论样本，用于产品机会识别与 Demo 验证，'
                               '不代表 Amazon 全量消费者意见。'))
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
        reviews = (source.data or []) if source.source_type == 'REAL_REVIEW' else []
        aliases = {}
        config_path = data_root / 'config' / 'amazon_competitors.json'
        if config_path.exists():
            aliases = {str(item.get('asin') or '').upper(): f"{item.get('brand', '')} {item.get('model', '')}".strip()
                       for item in json.loads(config_path.read_text(encoding='utf-8')) if item.get('asin')}
        return _real_voc(state, reviews, llm_provider, amazon_feedback, aliases)
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
