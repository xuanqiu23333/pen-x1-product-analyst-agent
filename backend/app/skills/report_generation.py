from pydantic import BaseModel
from app.schemas.state import AnalysisState
class ReportLanguage(BaseModel): markdown: str

def _real_voc_smoke_report(state: AnalysisState) -> dict:
    voc = state.voc
    review_count = int(voc.get('review_count', 0) or 0)
    source_counts = voc.get('source_counts', {})
    product_counts = voc.get('product_review_counts', {})
    lines = [
        '# PEN-X1 Real VOC Smoke Report', '',
        '## Data Coverage',
        f"- 真实评论：{review_count} 条；覆盖等级：**{voc.get('coverage_level', 'NEED_DATA')}**。",
        f"- 数据源：APIFY_REAL {source_counts.get('APIFY_REAL', 0)} 条；IMPORTED_REAL {source_counts.get('IMPORTED_REAL', 0)} 条；BRIGHTDATA_REAL {source_counts.get('BRIGHTDATA_REAL', 0)} 条；SAMPLE 0 条。",
        f"- 可读来源统计：Apify API：{source_counts.get('APIFY_REAL', 0)} 条；真实 CSV：{source_counts.get('IMPORTED_REAL', 0)} 条；Bright Data API：{source_counts.get('BRIGHTDATA_REAL', 0)} 条。",
        f"- Amazon SP-API：{state.project.get('data_provider_status', {}).get('Amazon SP-API', {}).get('status', 'NOT_CONFIGURED')}。",
        f"- 语义分类状态：{voc.get('status', 'NEED_DATA')}；分类方式：{voc.get('classification_source', 'UNAVAILABLE')}。",
        '', '## Product Review Counts',
    ]
    if product_counts:
        lines.extend(f'- {name}：{count} 条' for name, count in product_counts.items())
    else:
        lines.append('- 暂无有效真实评论。')
    lines += ['', '## Rating Distribution']
    for product, distribution in voc.get('rating_distribution', {}).items():
        ratings = '；'.join(f'{rating} 星 {count} 条' for rating, count in distribution.items())
        lines.append(f'- {product}：{ratings or "无"}')
    if not voc.get('rating_distribution'):
        lines.append('- 暂无评分分布。')
    lines += ['', '## Canonical Pain Points']
    points = voc.get('canonical_pain_points', [])
    if points:
        lines += [
            '| Pain Point | Mentions | Product Rate | Corpus Rate | Affected Products | Evidence Count |',
            '|---|---:|---|---|---|---:|',
        ]
    for point in points:
        evidence_ids = '、'.join(point.get('evidence_ids', [])) or '无'
        raw_wordings = '；'.join(point.get('raw_pain_points', [])) or '无'
        distribution = point.get('product_distribution', {})
        product_rate = '；'.join(
            f"{float(stats.get('mention_rate', 0)):.2%} of {product} reviews"
            f" ({stats.get('mentions', 0)}/{stats.get('sample_size', 0)})"
            for product, stats in distribution.items()) or '无'
        corpus_rate = (
            f"{float(point.get('corpus_mention_rate', 0)):.2%} of all REAL reviews"
            f" ({point.get('mentions', 0)}/{point.get('corpus_sample_size', review_count)})")
        lines.append(
            f"| {point.get('canonical_pain_point', '未命名痛点')} | {point.get('mentions', 0)} | "
            f"{product_rate} | {corpus_rate} | {'、'.join(point.get('products', [])) or '未知'} | "
            f"{len(point.get('evidence_ids', []))} |"
        )
        lines.append(f"  - 原始表述：{raw_wordings}；Evidence：{evidence_ids}。")
    if not points:
        lines.append('- 尚未形成真实语义痛点结论；不会使用规则或示例数据补写。')
    lines += ['', '## Positive Signals']
    for signal in voc.get('positive_feedback', []):
        lines.append(
            f"- {signal.get('signal', signal.get('aspect', '正向信号'))}："
            f"{signal.get('mention_count', 0)}/{signal.get('sample_size', review_count)} 条；"
            f"Evidence：{'、'.join(signal.get('evidence_ids', [])) or '无'}。"
        )
    if not voc.get('positive_feedback'):
        lines.append('- 尚无已验证的正向语义聚合结论。')
    lines += ['', '## Purchase Drivers']
    for driver in voc.get('purchase_drivers', []):
        lines.append(
            f"- {driver.get('topic', driver.get('driver', '购买驱动'))}："
            f"{driver.get('mention_count', 0)}/{driver.get('sample_size', review_count)} 条；"
            f"Evidence：{'、'.join(driver.get('evidence_ids', [])) or '无'}。"
        )
    if not voc.get('purchase_drivers'):
        lines.append('- 尚无评论明确表达且通过 Evidence 校验的购买驱动。')
    lines += ['', '## Cross-product Comparison']
    verified = voc.get('verified_purchase_ratio', {})
    helpful = voc.get('helpful_vote_signals', {})
    for product, count in product_counts.items():
        signal = helpful.get(product, {})
        insight = voc.get('product_insights', {}).get(product, {})
        top_point = (insight.get('canonical_pain_points') or insight.get('pain_points') or [None])[0]
        top_text = (f"；最高频痛点 {top_point.get('canonical_pain_point', top_point.get('pain_point'))} "
                    f"{top_point.get('mentions', top_point.get('mention_count'))}/{top_point.get('sample_size')} 条；"
                    f"Evidence：{'、'.join(top_point.get('evidence_ids', top_point.get('evidence_review_ids', []))) or '无'}"
                    if top_point else '；尚无已验证的语义痛点')
        lines.append(
            f"- {product}：{count} 条；已验证购买占比 {float(verified.get(product, 0) or 0):.1%}；"
            f"有用票 {signal.get('helpful_votes', 0)}，获得有用票的评论 {signal.get('reviews_with_helpful_votes', 0)} 条"
            f"{top_text}。"
        )
    if not product_counts:
        lines.append('- 数据不足，无法进行跨商品比较。')
    lines += ['', '## Market Opportunities']
    for opportunity in state.opportunities:
        lines.append(
            f"- **{opportunity.get('title', '未命名机会')}**：支持评论 {opportunity.get('supporting_reviews', 0)} 条；"
            f"置信度 {opportunity.get('confidence', 'LOW')}；能力状态 {opportunity.get('product_capability', 'UNKNOWN / NEED_VERIFY')}；"
            f"Evidence：{'、'.join(opportunity.get('evidence_ids', [])) or '无'}。"
        )
    if not state.opportunities:
        lines.append('- 尚无满足 Evidence 绑定要求的市场机会。')
    lines += ['', '## Evidence References']
    referenced = []
    for point in points:
        referenced.extend(point.get('evidence_ids', []))
    for opportunity in state.opportunities:
        referenced.extend(opportunity.get('evidence_ids', []))
    for key in ('positive_feedback', 'purchase_drivers', 'usage_scenarios'):
        for conclusion in voc.get(key, []):
            referenced.extend(conclusion.get('evidence_ids', []))
    evidence_index = {item.id: item for item in state.evidence}
    for evidence_id in list(dict.fromkeys(referenced))[:12]:
        item = evidence_index.get(evidence_id)
        if item:
            lines.append(
                f"- {item.id}：{item.product_name or '未知商品'} / {item.asin or '未知 ASIN'} / "
                f"{item.rating if item.rating is not None else '未知'} 星 / {item.review_date or '日期未知'} / "
                f"来源 {item.source_type or 'UNKNOWN'}。"
            )
    if not referenced:
        lines.append('- 暂无语义结论所引用的评论 Evidence。')
    battery = state.fact_by_id('battery_configurations')
    price = state.fact_by_id('target_price_usd')
    lines += [
        '', '## Data Limitations',
        '- 当前结论基于已获取的真实 Amazon 评论样本，用于产品机会识别及系统验证，不代表 Amazon 全量消费者意见。',
        f"- 已知 PEN-X1 事实：电池配置 {battery.value if battery else 'UNKNOWN / NEED_VERIFY'}；目标价格 {price.value if price else 'UNKNOWN / NEED_VERIFY'} 美元。",
        '- PEN-X1 的 lumens、runtime、IP rating、thermal、size、weight、certification：**UNKNOWN / NEED_VERIFY**。',
        '- 本报告不包含评论者姓名、个人主页或用户标识。',
    ]
    return {'title': 'PEN-X1 Real VOC Smoke Report', 'status': 'DRAFT', 'markdown': '\n'.join(lines)}

def run_report_generation(state: AnalysisState,llm_provider=None,mode: str='DEMO')->dict:
    real = mode.upper() == 'REAL'
    if real:
        return _real_voc_smoke_report(state)
    review_label = '真实评论' if real else '示例评论'
    source_counts = state.voc.get('source_counts', {})
    review_notice = (f"真实评论：{state.voc.get('review_count',0)} 条（Bright Data API：{source_counts.get('BRIGHTDATA_REAL',0)} 条，"
                     f"Apify API：{source_counts.get('APIFY_REAL',0)} 条，CSV 导入：{source_counts.get('IMPORTED_REAL',0)} 条）；"
                     f"VOC 状态：{state.voc.get('status','NEED_DATA')}。"
                     '来源身份已保留；未混入演示样例。' if real else
                     f"示例评论：{state.voc.get('review_count',0)} 条；仅供离线演示。")
    lines=['# PEN-X1 北美市场产品调研与上市可行性分析报告','','## 执行摘要',
           'PEN-X1 当前建议为**有条件推进**。报告结论来自结构化 Fact、Evidence、风险、关卡与 Python 计算，未提供参数保持未知或需验证。',
           '', '## 数据覆盖说明',
           f"内部事实：{len(state.facts)} 项；证据：{len(state.evidence)} 条；{review_label}：{state.voc.get('review_count',0)} 条；市场数据状态：{state.project.get('data_provider_status',{}).get('市场数据',{}).get('source_type','UNKNOWN')}。",
           review_notice, '', '## 市场、机会与风险',
           '供电灵活性仅在 VOC、竞品、市场与产品 Fact 同时引用时作为推断型候选机会。电池识别、BOOST、14500 温升、机械公差、EOL 与运输合规仍需验证。',
           '', '## 产品关卡与决策']
    for gate in state.decision.get('gates',[]): lines.append(f"- {gate['name']}：**{gate['status']}** —— {gate['reason']}")
    lines += ['','## 后续验证计划','1. 执行按电池配置、品牌、电量、温度和模式划分的兼容性测试。','2. 完成温升、机械接触、EOL、运输合规和页面理解度验证。','3. 补充佣金、FBA、运费和广告等实际成本，重新计算利润。']
    amazon=state.project.get('data_provider_status',{})
    live=amazon.get('Amazon SP-API',{}).get('status')=='LIVE'
    source_notice=(f"Amazon SP-API 生产数据：Catalog {amazon.get('Amazon Catalog',{}).get('count',0)} 条，"
                   f"Pricing {amazon.get('Amazon Pricing',{}).get('count',0)} 条，"
                   f"Customer Feedback {state.voc.get('amazon_feedback_topics',0)} 个官方聚合主题；"
                   'CSV 原始评论与主题提及次数分别统计。' if live else
                   'Amazon SP-API 实时数据未接入；竞品仍可能使用官网或 Fixture；原始评论来自 SQLite 中已校验的真实评论来源。' if real else
                   'Amazon SP-API 实时数据未接入；当前竞品与评论主要使用 Fixture / CSV 示例数据。')
    lines[7:7]=['','## Amazon 数据来源',source_notice]
    fallback='\n'.join(lines)
    if mode.upper()=='REAL' and llm_provider is not None:
        try:
            generated=ReportLanguage.model_validate(llm_provider.complete_json('仅返回 JSON：{"markdown":"中文报告"}。根据 AnalysisState 写报告，不得增加没有 Fact 或 Evidence 支持的参数；真实 VOC 未完成时不得声称已分析评论。',{'facts':[f.model_dump() for f in state.facts],'decision':state.decision,'voc_status':state.voc.get('status'),'review_count':state.voc.get('review_count',0),'review_source_notice':review_notice,'amazon_source_notice':source_notice,'validation_rules':'未知内容不可确定性表达'})); state.project.setdefault('llm_skill_calls',[]).append('最终报告'); fallback=(generated.markdown or fallback)+'\n\n## 数据来源校验\n'+review_notice+'\n\n## Amazon 数据来源\n'+source_notice
        except Exception as error: state.project.setdefault('warnings',[]).append(f'报告模型生成不可用：{error}')
    return {'title':'PEN-X1 北美市场产品调研与上市可行性分析报告','status':'DRAFT','markdown':fallback}
