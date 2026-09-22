import re
from app.schemas.models import Claim, ValidationResult
from app.schemas.state import AnalysisState
from app.services.review_cleaning import review_coverage_level

REAL_REVIEW_SOURCES = {'APIFY_REAL', 'BRIGHTDATA_REAL', 'IMPORTED_REAL'}

def _validation_result(errors: list[str], warnings: list[str]) -> ValidationResult:
    status = 'FAIL' if errors else 'WARN' if warnings else 'PASS'
    return ValidationResult(passed=not errors, status=status, warnings=warnings, errors=errors)

def validate_claims(state: AnalysisState, claims: list[Claim]) -> ValidationResult:
    fact_ids={fact.id for fact in state.facts}; evidence_ids={item.id for item in state.evidence}; errors=[]; warnings=[]
    for claim in claims:
        facts_ok=not claim.fact_ids or all(item in fact_ids for item in claim.fact_ids)
        evidence_ok=not claim.evidence_ids or all(item in evidence_ids for item in claim.evidence_ids)
        if claim.status=='UNSUPPORTED' or not facts_ok or not evidence_ok: errors.append(f'声明不可支持：{claim.text}')
        elif claim.status in {'INFERRED','NEED_VERIFY','CONFLICT'}: warnings.append(f'声明需谨慎表达：{claim.text}')
    return _validation_result(errors, warnings)

def extract_claims(state: AnalysisState) -> list[Claim]:
    claims=[]
    if state.fact_by_id('battery_configurations'):
        claims.append(Claim(claim_id='claim-battery-configurations',text='PEN-X1 支持五种电池配置',claim_type='product_fact',fact_ids=['battery_configurations'],status='SUPPORTED'))
    claim_index = 0
    for line in state.report.get('markdown','').splitlines():
        evidence_ids = re.findall(r'ev-review-[A-Za-z0-9_-]+', line)
        for match in re.finditer(r'\b\d+\s*(?:流明|lumen|小时|hour|IP\d+)', line, re.I):
            claim_index += 1
            claims.append(Claim(
                claim_id=f'claim-numeric-{claim_index}', text=match.group(0), claim_type='numeric',
                evidence_ids=list(dict.fromkeys(evidence_ids)),
                status='SUPPORTED' if evidence_ids else 'UNSUPPORTED',
            ))
    return claims

def validate_report(state: AnalysisState) -> ValidationResult:
    claims=state.report.get('claims') or extract_claims(state)
    parsed=[item if isinstance(item,Claim) else Claim.model_validate(item) for item in claims]
    state.report['claims']=[item.model_dump() for item in parsed]
    claim_result = validate_claims(state,parsed)
    errors = list(claim_result.errors)
    warnings = list(claim_result.warnings)
    if state.project.get('mode') == 'REAL_MODE':
        review_evidence = [item for item in state.evidence if item.id.startswith('ev-review-')]
        evidence_index = {item.id: item for item in review_evidence}
        review_count = int(state.voc.get('review_count', 0) or 0)
        if state.voc.get('status') != 'COMPLETED':
            errors.append('真实 VOC 尚未完成结构化语义分析。')
        if len(review_evidence) != review_count:
            errors.append(f'真实评论计数与 Evidence 不一致：VOC={review_count}，Evidence={len(review_evidence)}。')
        for item in review_evidence:
            if item.source_type not in REAL_REVIEW_SOURCES or item.data_nature == 'SAMPLE':
                errors.append(f'评论 Evidence {item.id} 不是允许的真实评论来源。')
        source_counts = state.voc.get('source_counts', {})
        if int(source_counts.get('SAMPLE', 0) or 0) != 0:
            errors.append('REAL_MODE 不允许混入 SAMPLE 评论。')
        expected_coverage = review_coverage_level(review_count)
        actual_coverage = state.voc.get('coverage_level')
        if actual_coverage != expected_coverage:
            errors.append(f'覆盖等级不一致：应为 {expected_coverage}，实际为 {actual_coverage}。')
        def validate_conclusion(point: dict, evidence_field: str) -> None:
            sample_size = int(point.get('sample_size', review_count) or 0)
            mention_count = int(point.get('mention_count', point.get('mentions', 0)) or 0)
            mention_rate = float(point.get('mention_rate', point.get('frequency', 0)) or 0)
            label = point.get('topic') or point.get('pain_point') or point.get('signal') or '未命名结论'
            if mention_count > sample_size:
                errors.append(f"结论“{label}”提及数超过样本数。")
            expected_rate = round(mention_count / sample_size, 4) if sample_size else 0
            if abs(mention_rate - expected_rate) > 0.0001:
                errors.append(f"结论“{label}”提及率与 Python 统计不一致。")
            evidence_ids = list(dict.fromkeys(point.get(evidence_field, [])))
            if not evidence_ids:
                errors.append(f"结论“{label}”没有真实 Review Evidence。")
            if mention_count != len(evidence_ids):
                errors.append(f"结论“{label}”提及数与 Evidence 数量不一致。")
            for evidence_id in evidence_ids:
                if evidence_id not in evidence_index:
                    errors.append(f'结论引用的 Evidence 不存在：{evidence_id}。')
        for point in state.voc.get('pain_points', []):
            validate_conclusion(point, 'evidence_review_ids')
        canonical_names = set()
        canonical_evidence: dict[str, set[str]] = {}
        product_review_counts = state.voc.get('product_review_counts', {})
        for point in state.voc.get('canonical_pain_points', []):
            name = point.get('canonical_pain_point') or '未命名 Canonical Pain Point'
            canonical_names.add(name)
            evidence_ids = point.get('evidence_ids', [])
            unique_ids = list(dict.fromkeys(evidence_ids))
            canonical_evidence[name] = set(unique_ids)
            mentions = int(point.get('mentions', 0) or 0)
            if mentions != len(unique_ids):
                errors.append(f'Canonical Pain Point“{name}”提及数与唯一 Evidence 数量不一致。')
            if not point.get('raw_pain_points'):
                errors.append(f'Canonical Pain Point“{name}”的 raw_pain_points 至少需要 1 条。')
            corpus_size = int(point.get('corpus_sample_size', 0) or 0)
            corpus_rate = float(point.get('corpus_mention_rate', -1))
            product_size = int(point.get('product_sample_size', 0) or 0)
            product_rate = float(point.get('product_mention_rate', -1))
            if corpus_size != review_count:
                errors.append(f'Canonical Pain Point“{name}”的 corpus_sample_size 与真实评论总数不一致。')
            expected_corpus_rate = round(mentions / corpus_size, 4) if corpus_size else 0
            if not 0 <= corpus_rate <= 1 or abs(corpus_rate - expected_corpus_rate) > 0.0001:
                errors.append(f'Canonical Pain Point“{name}”的 corpus_mention_rate 不正确。')
            expected_product_rate = round(mentions / product_size, 4) if product_size else 0
            if not 0 <= product_rate <= 1 or abs(product_rate - expected_product_rate) > 0.0001:
                errors.append(f'Canonical Pain Point“{name}”的 product_mention_rate 不正确。')
            distribution = point.get('product_distribution', {})
            distribution_mentions = 0
            distribution_sample_size = 0
            for product, product_stats in distribution.items():
                product_mentions = int(product_stats.get('mentions', 0) or 0)
                sample = int(product_stats.get('sample_size', 0) or 0)
                rate = float(product_stats.get('mention_rate', -1))
                distribution_mentions += product_mentions
                distribution_sample_size += sample
                expected_sample = int(product_review_counts.get(product, sample) or 0)
                if sample != expected_sample:
                    errors.append(f'Canonical Pain Point“{name}”中 {product} 的 sample_size 不正确。')
                expected_rate = round(product_mentions / sample, 4) if sample else 0
                if not 0 <= rate <= 1 or abs(rate - expected_rate) > 0.0001:
                    errors.append(f'Canonical Pain Point“{name}”中 {product} 的 mention_rate 不正确。')
            if distribution_mentions != mentions:
                errors.append(f'Canonical Pain Point“{name}”的 product_distribution mentions 之和不等于 mentions。')
            if distribution_sample_size != product_size:
                errors.append(f'Canonical Pain Point“{name}”的 product_sample_size 与产品分布样本数不一致。')
            validate_conclusion(point, 'evidence_ids')
        for key in ('positive_feedback', 'usage_scenarios', 'purchase_drivers', 'recurring_complaints'):
            for conclusion in state.voc.get(key, []):
                validate_conclusion(
                    conclusion,
                    'evidence_review_ids' if 'evidence_review_ids' in conclusion else 'evidence_ids',
                )
        for insight in state.voc.get('product_insights', {}).values():
            for point in insight.get('pain_points', []):
                validate_conclusion(point, 'evidence_review_ids')
            for key in ('positive_feedback', 'usage_scenarios', 'purchase_drivers', 'recurring_complaints'):
                for conclusion in insight.get(key, []):
                    validate_conclusion(
                        conclusion,
                        'evidence_review_ids' if 'evidence_review_ids' in conclusion else 'evidence_ids',
                    )
        opportunity_bindings: set[str] = set()
        for opportunity in state.opportunities:
            bound_points = opportunity.get('canonical_pain_points', [])
            if not bound_points:
                errors.append(f"机会“{opportunity.get('title', '未命名机会')}”未绑定 canonical pain point。")
            for name in bound_points:
                if name not in canonical_names:
                    errors.append(f'机会绑定的 canonical pain point 不存在：{name}。')
                if name in opportunity_bindings:
                    errors.append(f'Canonical Pain Point“{name}”重复生成多个 Market Opportunity。')
                opportunity_bindings.add(name)
            opportunity_evidence = set(opportunity.get('evidence_ids', opportunity.get('voc_evidence', [])))
            bound_evidence = set().union(*(canonical_evidence.get(name, set()) for name in bound_points))
            if opportunity_evidence - bound_evidence:
                errors.append(
                    f"机会“{opportunity.get('title', '未命名机会')}”的 Evidence 不属于所绑定的 canonical pain point。")
            for evidence_id in opportunity.get('evidence_ids', opportunity.get('voc_evidence', [])):
                if evidence_id not in evidence_index:
                    errors.append(f'机会引用的真实评论 Evidence 不存在：{evidence_id}。')
        if expected_coverage != 'GOOD_COVERAGE':
            warnings.append(f'真实评论覆盖等级为 {expected_coverage}，结论仅用于 Demo 机会识别。')
        if 'UNKNOWN / NEED_VERIFY' not in state.report.get('markdown', ''):
            errors.append('报告未明确标注未知产品参数为 UNKNOWN / NEED_VERIFY。')
    return _validation_result(errors, warnings)
