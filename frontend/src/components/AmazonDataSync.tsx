import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getAmazonSync, syncAmazonData } from '../api'
import { chinese } from '../display'
import type { AmazonSyncSnapshot } from '../types'

export function AmazonDataSync({onAnalyzeReal,analysisBusy=false}:{onAnalyzeReal:()=>void;analysisBusy?:boolean}) {
  const [snapshot, setSnapshot] = useState<AmazonSyncSnapshot | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { getAmazonSync().then(setSnapshot).catch(() => setError('暂时无法读取同步状态。')) }, [])
  async function sync() {
    setBusy(true); setError('')
    try { await syncAmazonData(); setSnapshot(await getAmazonSync()) }
    catch (cause) { setError(cause instanceof Error ? cause.message : '同步失败。') }
    finally { setBusy(false) }
  }
  const summary = snapshot?.summary
  const status = snapshot?.connection_status ?? 'PENDING'
  return <section className="amazon-sync" aria-label="亚马逊数据同步">
    <div className="amazon-sync-head"><div><span className="section-label">Amazon Data Sync</span><h2>亚马逊官方数据同步</h2><p>商品目录、价格与官方聚合反馈；原始评论继续由 CSV 提供。</p></div>
      <div className="amazon-sync-actions"><button onClick={sync} disabled={busy || analysisBusy}><RefreshCw size={15}/>{busy ? '同步中…' : '同步亚马逊数据（Sync Amazon Data）'}</button>{status==='LIVE' && <button onClick={onAnalyzeReal} disabled={busy || analysisBusy}>使用已同步数据分析</button>}</div></div>
    <div className="amazon-sync-meta" aria-live="polite"><span>Amazon SP-API：<b>{chinese(status)}</b></span><span>上次同步：{summary?.finished_at ? new Date(summary.finished_at).toLocaleString('zh-CN') : '尚无'}</span><span>结果：{chinese(summary?.status ?? 'PENDING')}</span></div>
    <div className="amazon-sync-counts"><span>目标竞品 <b>{summary?.target_products ?? 0}</b></span><span>成功商品 <b>{summary?.successful_products ?? 0}</b></span><span>目录记录 <b>{summary?.catalog_records ?? 0}</b></span><span>价格记录 <b>{summary?.pricing_records ?? 0}</b></span><span>反馈主题 <b>{summary?.feedback_topics ?? 0}</b></span></div>
    {!!summary?.products?.length && <ul className="amazon-sync-products">{summary.products.map((item,index)=><li key={`${item.brand}-${index}`}>{item.brand} {item.model}：{chinese(item.status)}{item.asin ? ` · ${item.asin}` : ''}</li>)}</ul>}
    {status==='NOT_CONFIGURED' && <p className="amazon-sync-note">Amazon SP-API 尚未配置，当前使用演示数据。</p>}
    {summary?.products?.some(item => item.status==='ASIN_REQUIRED') && <p className="amazon-sync-note">部分竞品需要在配置文件中填写 ASIN。</p>}
    {summary?.mode==='sandbox' && <p className="amazon-sync-note">沙箱仅返回模拟响应，不能作为真实市场结论。</p>}
    {error && <p className="error" role="alert">{error}</p>}
  </section>
}
