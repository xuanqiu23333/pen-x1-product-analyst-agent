import type { AnalysisState, PainPoint } from '../types'
import { chinese, localizeJson } from '../display'

export function ResultPanel({ state, skillId, onEvidence }: {
  state: AnalysisState; skillId: string; onEvidence: (id: string) => void
}) {
  if (skillId === '04') {
    const real = state.project.mode === 'REAL_MODE'
    const painPoints = state.voc.pain_points ?? []
    return <section>
      <div className="section-label">用户之声分析 · {real ? '真实 CSV 导入' : '示例演示数据'}</div>
      <h2>用户痛点与原始证据</h2>
      <p className="subtle">{real
        ? `有效真实导入评论 ${state.voc.review_count ?? 0} 条；${chinese(state.voc.coverage_level ?? 'NEED_DATA')}。导入来源未经 Amazon 平台独立核验。`
        : `已处理 ${state.voc.review_count ?? 0} 条示例评论；不是实时亚马逊数据。`}</p>
      {real && state.voc.status === 'NEED_DATA' && <p className="review-alert" role="status">暂无有效真实评论，VOC 需要数据；不会自动使用演示样例。</p>}
      {real && state.voc.status === 'NEED_LLM' && <p className="review-alert" role="status">评论已入库，但 DeepSeek 结构化分析尚未完成。不会用规则分类冒充真实 VOC。</p>}
      <div className="pain-grid">{painPoints.map((point: PainPoint) => <article
        className="pain-card" key={`${point.aspect}-${point.pain_point}`}>
        <button type="button" className="pain-card-main" aria-label={`查看${point.pain_point}的第一条评论证据`}
          onClick={() => onEvidence(point.evidence_review_ids[0])}>
          <span>{chinese(point.severity)}</span><strong>{point.pain_point}</strong>
          <b>{point.mentions} 次提及</b>
          {real && point.avg_rating != null && <small>平均评分 {point.avg_rating.toFixed(1)} / 5 · 占比 {(point.frequency * 100).toFixed(1)}%</small>}
          <small>点击查看评论证据 →</small>
        </button>
        {real && point.evidence_review_ids.length > 1 && <details className="pain-evidence-list">
          <summary>逐条查看 {point.evidence_review_ids.length} 条证据</summary>
          <div>{point.evidence_review_ids.map((id, index) => <button type="button" key={id}
            onClick={() => onEvidence(id)} aria-label={`查看${point.pain_point}的第 ${index + 1} 条评论证据`}>
            评论证据 {index + 1}
          </button>)}</div>
        </details>}
      </article>)}</div>
    </section>
  }
  if (skillId === '10') return <section><div className="section-label">最终报告 · {chinese(state.report.status)}</div><h2>北美市场产品调研与上市可行性分析报告</h2><pre className="report">{state.report.markdown}</pre></section>
  const names: Record<string, string> = {'01':'资料完整性检查','02':'北美市场调研','03':'四款竞品分析','05':'市场机会挖掘','06':'产品技术风险','07':'研发 / 量产 / 海外上市风险','08':'价格与利润分析','09':'优势劣势机会威胁与产品决策'}
  const source = skillId === '03' ? state.competitors : skillId === '05' ? state.opportunities : skillId === '06' ? state.technical_risks : skillId === '07' ? state.lifecycle_risks : skillId === '08' ? state.profit_analysis : skillId === '09' ? state.decision : state.market
  return <section><div className="section-label">第 {skillId} 步 · 结构化结果</div><h2>{names[skillId]}</h2><pre className="result-json">{localizeJson(source)}</pre></section>
}
