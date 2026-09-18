import { useEffect, useState, type FormEvent } from 'react'
import { FileUp } from 'lucide-react'
import { getReviewStats, importReviewCsv } from '../api'
import { chinese } from '../display'
import type { ReviewImportSummary, ReviewStats } from '../types'

export function RealReviewData({ onAnalyzeReal, analysisBusy = false }: {
  onAnalyzeReal: () => void; analysisBusy?: boolean
}) {
  const [stats, setStats] = useState<ReviewStats | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [lastRun, setLastRun] = useState<ReviewImportSummary | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { getReviewStats().then(setStats).catch(() => setError('暂时无法读取真实评论统计，请检查后端服务。')) }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) { setError('请先选择 UTF-8 编码的 CSV 文件。'); return }
    setBusy(true); setError(''); setLastRun(null)
    try {
      const imported = await importReviewCsv(file)
      setLastRun(imported)
      setStats(await getReviewStats())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '评论导入失败。')
    } finally { setBusy(false) }
  }

  const fields = [
    ['原始评论', stats?.raw_reviews ?? 0], ['有效评论', stats?.valid_reviews ?? 0],
    ['重复评论', stats?.duplicate_reviews ?? 0], ['无效评论', stats?.invalid_reviews ?? 0],
    ['真实占比', `${stats?.real_percent ?? 0}%`], ['样例占比', `${stats?.sample_percent ?? 0}%`],
  ] as const

  return <section className="review-sync" aria-label="真实评论数据">
    <div className="review-sync-head">
      <div><span className="section-label">真实评论数据</span><h2>CSV 导入与覆盖情况</h2>
        <p>仅导入你有权使用的评论。导入来源未经 Amazon 平台独立核验；演示样例不会进入真实 VOC。</p></div>
      <button type="button" onClick={onAnalyzeReal} disabled={busy || analysisBusy}>运行真实评论分析</button>
    </div>
    <form className="review-import" onSubmit={submit}>
      <label htmlFor="review-csv">选择 UTF-8 评论 CSV</label>
      <input id="review-csv" type="file" accept=".csv,text/csv" onChange={event => setFile(event.target.files?.[0] ?? null)} />
      <button type="submit" disabled={busy || analysisBusy}><FileUp size={16}/>{busy ? '导入中…' : '导入真实评论'}</button>
    </form>
    <div className="review-counts">{fields.map(([label, value]) => <span key={label}>{label}<b>{value}</b></span>)}</div>
    <div className="review-coverage"><span>覆盖等级：<b>{chinese(stats?.coverage_level ?? 'NEED_DATA')}</b></span>
      <span>最近采集：{stats?.last_collected ? new Date(stats.last_collected).toLocaleString('zh-CN') : '尚无'}</span></div>
    <p className="review-note">项目内部演示等级：0 条需数据；1–49 条低覆盖；50–199 条部分覆盖；200 条及以上达到演示覆盖。并非行业统计标准。</p>
    <div className="review-products" aria-label="竞品评论数量">
      {Object.entries(stats?.products ?? {}).map(([name, count]) => <span key={name}>{name}<b>{count} 条</b></span>)}
    </div>
    {lastRun && <p className="review-success" role="status">导入完成：采集 {lastRun.collected_reviews} 条，有效 {lastRun.valid_reviews} 条，重复 {lastRun.duplicate_reviews} 条，无效 {lastRun.invalid_reviews} 条。</p>}
    {error && <p className="error" role="alert">{error}</p>}
  </section>
}
