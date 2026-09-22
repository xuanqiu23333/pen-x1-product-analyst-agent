import { useEffect, useState, type FormEvent } from 'react'
import { CloudDownload, FileUp } from 'lucide-react'
import { collectRealReviews, getLatestReviewCollection, getReviewStats, importReviewCsv } from '../api'
import { chinese } from '../display'
import type { ReviewCollectionSummary, ReviewImportSummary, ReviewStats } from '../types'

const statusMessages: Record<string, string> = {
  NOT_CONFIGURED: 'Bright Data API 尚未配置，请在本地 .env 中填写 Token。',
  APIFY_NOT_CONFIGURED: 'Apify API 尚未配置，请在本地 .env 中填写 Token。',
  PRODUCT_URL_REQUIRED: '竞品商品链接尚未填写；系统不会猜测或自动补全链接。',
  SCHEMA_CONFIRMATION_REQUIRED: '请先执行一款商品五条评论验证，人工确认字段结构后再开放批量采集。',
  PARTIAL: '部分商品未完成，请查看各商品状态和真实返回数量。',
  FAILED: '本次 API 采集失败，未使用样例评论补足数据。',
  COMPLETED: '本次 API 采集已完成；展示数量均来自实际返回和入库结果。',
  PENDING: '尚未执行真实评论采集。',
}

export function RealReviewData({ onAnalyzeReal, analysisBusy = false }: {
  onAnalyzeReal: () => void; analysisBusy?: boolean
}) {
  const [stats, setStats] = useState<ReviewStats | null>(null)
  const [collection, setCollection] = useState<ReviewCollectionSummary | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [lastImport, setLastImport] = useState<ReviewImportSummary | null>(null)
  const [importBusy, setImportBusy] = useState(false)
  const [collectBusy, setCollectBusy] = useState(false)
  const [error, setError] = useState('')
  const busy = importBusy || collectBusy || analysisBusy

  useEffect(() => {
    Promise.all([getReviewStats(), getLatestReviewCollection()])
      .then(([reviewStats, latest]) => { setStats(reviewStats); setCollection(latest) })
      .catch(() => setError('暂时无法读取真实评论统计，请检查后端服务。'))
  }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) { setError('请先选择 UTF-8 编码的 CSV 文件。'); return }
    setImportBusy(true); setError(''); setLastImport(null)
    try {
      const imported = await importReviewCsv(file)
      setLastImport(imported)
      setStats(await getReviewStats())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '评论导入失败。')
    } finally { setImportBusy(false) }
  }

  async function collect() {
    setCollectBusy(true); setError(''); setLastImport(null)
    try {
      const probeMode = collection?.status === 'SCHEMA_CONFIRMATION_REQUIRED' || collection?.schema_confirmation_required
      const result = await collectRealReviews(probeMode ? 5 : 100)
      setCollection(result)
      setStats(await getReviewStats())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '真实评论采集失败。')
    } finally { setCollectBusy(false) }
  }

  const fields = [
    ['原始评论', stats?.raw_reviews ?? 0], ['有效评论', stats?.valid_reviews ?? 0],
    ['重复评论', stats?.duplicate_reviews ?? 0], ['无效评论', stats?.invalid_reviews ?? 0],
    ['真实占比', `${stats?.real_percent ?? 0}%`], ['样例占比', `${stats?.sample_percent ?? 0}%`],
  ] as const
  const collectionStatus = collectBusy ? 'COLLECTING' : collection?.status ?? 'PENDING'
  const providerName = collection?.provider === 'BRIGHTDATA' ? 'Bright Data' : collection?.provider === 'APIFY' ? 'Apify' : '未配置'
  const probeMode = collection?.status === 'SCHEMA_CONFIRMATION_REQUIRED' || collection?.schema_confirmation_required
  const collectionFields = [
    ['数据源', providerName],
    ['最近运行', collection?.finished_at ? new Date(collection.finished_at).toLocaleString('zh-CN') : '尚无'],
    ['目标评论', collection?.target_reviews ?? 400],
    ['实际请求', collection?.requested_reviews ?? 0],
    ['实际获取', collection?.collected_reviews ?? 0],
    ['有效评论', collection?.valid_reviews ?? 0],
    ['重复评论', collection?.duplicate_reviews ?? 0],
    ['无效评论', collection?.invalid_reviews ?? 0],
  ] as const

  return <section className="review-sync" aria-label="真实评论数据">
    <div className="review-sync-head">
      <div><span className="section-label">真实评论数据</span><h2>接口采集、CSV 导入与覆盖情况</h2>
        <p>Apify、Bright Data 或 CSV 提供真实数据，统一数据层负责清洗、去重和证据追溯；演示样例不会进入真实 VOC。</p></div>
      <button type="button" onClick={onAnalyzeReal} disabled={busy}>运行真实评论分析</button>
    </div>

    <div className="review-api-panel" aria-label="真实评论 API 采集">
      <div className="review-api-head">
        <div><strong>{providerName} API</strong><span className={`badge ${collectionStatus.toLowerCase()}`}>{chinese(collectionStatus)}</span></div>
        <button type="button" onClick={collect} disabled={busy} aria-busy={collectBusy}>
          <CloudDownload size={17}/>{collectBusy ? '正在获取真实评论…' : probeMode ? '执行一款商品五条字段验证' : '获取真实 Amazon 评论'}
        </button>
      </div>
      <p className="review-api-message" role="status" aria-live="polite">
        {collectBusy ? '采集任务正在执行，最多等待配置的轮询时限，请勿重复提交。' : statusMessages[collectionStatus] ?? chinese(collectionStatus)}
      </p>
      <div className="review-collection-counts">
        {collectionFields.map(([label, value]) => <span key={label}>{label}<b>{value}</b></span>)}
      </div>
      <div className="review-api-products" aria-label="各竞品采集数量">
        {(collection?.products ?? []).map(item => <article key={`${item.brand}-${item.model}`}>
          <div><strong>{item.brand} {item.model}</strong><span>{chinese(item.status)}</span></div>
          <p>实际获取 <b>{item.collected_reviews}</b> / 目标 {item.target_reviews}；有效 <b>{item.valid_reviews}</b></p>
        </article>)}
      </div>
    </div>

    <form className="review-import" onSubmit={submit}>
      <label htmlFor="review-csv">选择 UTF-8 评论 CSV</label>
      <input id="review-csv" type="file" accept=".csv,text/csv" onChange={event => setFile(event.target.files?.[0] ?? null)} />
      <button type="submit" disabled={busy}><FileUp size={16}/>{importBusy ? '导入中…' : '导入真实评论'}</button>
    </form>
    <div className="review-counts">{fields.map(([label, value]) => <span key={label}>{label}<b>{value}</b></span>)}</div>
    <div className="review-coverage"><span>覆盖等级：<b>{chinese(stats?.coverage_level ?? 'NEED_DATA')}</b></span>
      <span>最近采集：{stats?.last_collected ? new Date(stats.last_collected).toLocaleString('zh-CN') : '尚无'}</span></div>
    <p className="review-note">项目内部演示等级：0 条需数据；1–19 条低覆盖；20–49 条部分覆盖；50 条及以上良好覆盖。并非行业统计标准。</p>
    <p className="review-note">当前有效来源：Apify {stats?.sources?.APIFY_REAL ?? 0} 条；真实 CSV {stats?.sources?.IMPORTED_REAL ?? 0} 条；Bright Data {stats?.sources?.BRIGHTDATA_REAL ?? 0} 条；样例 0 条。共分析 {Object.values(stats?.products ?? {}).filter(count => count > 0).length} 款商品。</p>
    <div className="review-products" aria-label="竞品有效评论数量">
      {Object.entries(stats?.products ?? {}).filter(([, count]) => count > 0).map(([name, count]) => <span key={name}>{name}<b>{count} 条</b></span>)}
    </div>
    {lastImport && <p className="review-success" role="status">导入完成：采集 {lastImport.collected_reviews} 条，有效 {lastImport.valid_reviews} 条，重复 {lastImport.duplicate_reviews} 条，无效 {lastImport.invalid_reviews} 条。</p>}
    {error && <p className="error" role="alert">{error}</p>}
  </section>
}
