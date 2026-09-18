import type { AnalysisState, AmazonSyncSnapshot, AmazonSyncSummary } from './types'
const BASE_URL = 'http://localhost:8000/api'
export async function startAnalysis(mode:'DEMO'|'REAL'='DEMO'): Promise<AnalysisState> { const response = await fetch(`${BASE_URL}/analysis-runs`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode})}); if(!response.ok) throw new Error('无法连接后端，请先启动 FastAPI 服务。'); const run = await response.json(); const result = await fetch(`${BASE_URL}/analysis-runs/${run.run_id}`); return result.json() }

export async function getAmazonSync(): Promise<AmazonSyncSnapshot> { const response=await fetch(`${BASE_URL}/amazon/sync/latest`); if(!response.ok) throw new Error('无法读取亚马逊同步状态。'); return response.json() }
export async function syncAmazonData(): Promise<AmazonSyncSummary> { const response=await fetch(`${BASE_URL}/amazon/sync`,{method:'POST'}); if(!response.ok) throw new Error('亚马逊同步请求失败。'); return response.json() }
