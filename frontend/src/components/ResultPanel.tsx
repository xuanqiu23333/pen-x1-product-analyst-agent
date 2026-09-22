import type { AnalysisState, CanonicalPainPoint, PainPoint } from '../types'
import { chinese, localizeJson } from '../display'

export function ResultPanel({ state, skillId, onEvidence }: {
  state: AnalysisState; skillId: string; onEvidence: (id: string) => void
}) {
  if (skillId === '04') {
    const real = state.project.mode === 'REAL_MODE'
    const canonicalPoints = state.voc.canonical_pain_points ?? []
    const painPoints = state.voc.pain_points ?? []
    return <section>
      <div className="section-label">用户之声分析 · {real ? '真实 Amazon 评论' : '示例演示数据'}</div>
      <h2>聚合用户痛点与原始证据</h2>
      <p className="subtle">{real
        ? `有效真实评论 ${state.voc.review_count ?? 0} 条；Apify ${state.voc.source_counts?.APIFY_REAL ?? 0} 条；分析商品 ${state.voc.products_analyzed ?? 0} 款；样例 0 条；${chinese(state.voc.coverage_level ?? 'NEED_DATA')}。`
        : `已处理 ${state.voc.review_count ?? 0} 条示例评论；不是实时亚马逊数据。`}</p>
      {real && state.voc.status === 'NEED_DATA' && <p className="review-alert" role="status">暂无有效真实评论，VOC 需要数据；不会自动使用演示样例。</p>}
      {real && state.voc.status === 'NEED_LLM' && <p className="review-alert" role="status">评论已入库，但 DeepSeek 结构化分析尚未完成。不会用规则分类冒充真实 VOC。</p>}
      {real && canonicalPoints.length > 0 && <div className="pain-grid">{canonicalPoints.map((point: CanonicalPainPoint) => <article
        className="pain-card" key={`${point.aspect}-${point.canonical_pain_point}`}>
        <button type="button" className="pain-card-main" aria-label={`查看${point.canonical_pain_point}的第一条评论证据`}
          onClick={() => onEvidence(point.evidence_ids[0])}>
          <span>{chinese(point.confidence)}</span><strong>{point.canonical_pain_point}</strong>
          <b>{point.mentions} 条唯一评论支持</b>
          <small>产品内提及率 {(point.product_mention_rate * 100).toFixed(2)}%（{point.mentions}/{point.product_sample_size}）</small>
          <small>全部真实评论占比 {(point.corpus_mention_rate * 100).toFixed(2)}%（{point.mentions}/{point.corpus_sample_size}）</small>
          {Object.entries(point.product_distribution).map(([product, stats]) => <small key={product}>
            {product}：{(stats.mention_rate * 100).toFixed(2)}%（{stats.mentions}/{stats.sample_size}）
          </small>)}
          <small>点击查看评论证据 →</small>
        </button>
        <details className="pain-evidence-list">
          <summary>查看 {point.raw_pain_points.length} 条原始表述与 {point.evidence_ids.length} 条证据</summary>
          <div>{point.evidence_ids.map((id, index) => <button type="button" key={id}
            onClick={() => onEvidence(id)} aria-label={`查看${point.canonical_pain_point}的第 ${index + 1} 条评论证据`}>
            评论证据 {index + 1}
          </button>)}</div>
        </details>
      </article>)}</div>}
      {(!real || canonicalPoints.length === 0) && <div className="pain-grid">{painPoints.map((point: PainPoint) => <article
        className="pain-card" key={`${point.aspect}-${point.pain_point}`}>
        <button type="button" className="pain-card-main" aria-label={`查看${point.pain_point}的第一条评论证据`}
          onClick={() => onEvidence(point.evidence_review_ids[0])}>
          <span>{chinese(point.severity)}</span><strong>{point.pain_point}</strong>
          <b>{point.mention_count ?? point.mentions} / {point.sample_size ?? state.voc.review_count ?? 0} 条提及</b>
          {real && point.avg_rating != null && <small>平均评分 {point.avg_rating.toFixed(1)} / 5 · 占比 {((point.mention_rate ?? point.frequency) * 100).toFixed(1)}%</small>}
          <small>点击查看评论证据 →</small>
        </button>
        {real && point.evidence_review_ids.length > 1 && <details className="pain-evidence-list">
          <summary>逐条查看 {point.evidence_review_ids.length} 条证据</summary>
          <div>{point.evidence_review_ids.map((id, index) => <button type="button" key={id}
            onClick={() => onEvidence(id)} aria-label={`查看${point.pain_point}的第 ${index + 1} 条评论证据`}>
            评论证据 {index + 1}
          </button>)}</div>
        </details>}
      </article>)}</div>}
    </section>
  }
  if (skillId === '10') return <section><div className="section-label">最终报告 · {chinese(state.report.status)}</div><h2>{state.project.mode === 'REAL_MODE' ? 'PEN-X1 真实用户之声验证报告' : '北美市场产品调研与上市可行性分析报告'}</h2><pre className="report">{state.report.markdown}</pre></section>
  const names: Record<string, string> = {'01':'资料完整性检查','02':'北美市场调研','03':'四款竞品分析','05':'市场机会挖掘','06':'产品技术风险','07':'研发 / 量产 / 海外上市风险','08':'价格与利润分析','09':'优势劣势机会威胁与产品决策'}
  const source = skillId === '03' ? state.competitors : skillId === '05' ? state.opportunities : skillId === '06' ? state.technical_risks : skillId === '07' ? state.lifecycle_risks : skillId === '08' ? state.profit_analysis : skillId === '09' ? state.decision : state.market
  return <section><div className="section-label">第 {skillId} 步 · 结构化结果</div><h2>{names[skillId]}</h2><pre className="result-json">{localizeJson(source)}</pre></section>
}
