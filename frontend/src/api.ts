import type { AnalysisState } from './types'
const BASE_URL = 'http://localhost:8000/api'
export async function startDemo(): Promise<AnalysisState> { const response = await fetch(`${BASE_URL}/analysis-runs`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode:'DEMO'})}); if(!response.ok) throw new Error('无法连接后端，请先启动 FastAPI 服务。'); const run = await response.json(); const result = await fetch(`${BASE_URL}/analysis-runs/${run.run_id}`); return result.json() }
