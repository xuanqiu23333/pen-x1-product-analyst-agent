import type { AnalysisState, AmazonSyncSnapshot, AmazonSyncSummary, ReviewCollectionSummary, ReviewImportSummary, ReviewStats } from './types'
const BASE_URL = 'http://localhost:8000/api'
export async function startAnalysis(mode:'DEMO'|'REAL'='DEMO'): Promise<AnalysisState> { const response = await fetch(`${BASE_URL}/analysis-runs`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode})}); if(!response.ok) throw new Error('无法连接后端，请先启动 FastAPI 服务。'); const run = await response.json(); const result = await fetch(`${BASE_URL}/analysis-runs/${run.run_id}`); return result.json() }

export async function getAmazonSync(): Promise<AmazonSyncSnapshot> { const response=await fetch(`${BASE_URL}/amazon/sync/latest`); if(!response.ok) throw new Error('无法读取亚马逊同步状态。'); return response.json() }
export async function syncAmazonData(): Promise<AmazonSyncSummary> { const response=await fetch(`${BASE_URL}/amazon/sync`,{method:'POST'}); if(!response.ok) throw new Error('亚马逊同步请求失败。'); return response.json() }

export async function getReviewStats(): Promise<ReviewStats> {
  const response = await fetch(`${BASE_URL}/reviews/stats`)
  if (!response.ok) throw new Error('无法读取评论统计，请检查后端服务。')
  return response.json()
}

export async function importReviewCsv(file: File): Promise<ReviewImportSummary> {
  if (file.size > 5 * 1024 * 1024) throw new Error('CSV 文件不能超过 5 MB。')
  const response = await fetch(`${BASE_URL}/reviews/import`, {
    method: 'POST', headers: { 'Content-Type': 'text/csv; charset=utf-8' }, body: await file.text(),
  })
  if (!response.ok) {
    const result = await response.json().catch(() => ({}))
    throw new Error(typeof result.detail === 'string' ? result.detail : '评论导入失败，请检查 CSV 文件。')
  }
  return response.json()
}

export async function getLatestReviewCollection(): Promise<ReviewCollectionSummary> {
  const response = await fetch(`${BASE_URL}/reviews/collection/latest`)
  if (!response.ok) throw new Error('无法读取真实评论采集状态。')
  return response.json()
}

export async function collectRealReviews(maxReviewsPerProduct = 100): Promise<ReviewCollectionSummary> {
  const response = await fetch(`${BASE_URL}/reviews/collect`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({max_reviews_per_product: maxReviewsPerProduct}),
  })
  if (!response.ok) {
    const result = await response.json().catch(() => ({}))
    throw new Error(typeof result.detail === 'string' ? result.detail : '真实评论采集失败。')
  }
  return response.json()
}
