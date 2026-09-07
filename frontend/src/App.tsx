import { useMemo, useState } from 'react'
import { Activity, Play, ShieldCheck, Zap } from 'lucide-react'
import { startDemo } from './api'
import type { AnalysisState, Evidence } from './types'
import { chinese } from './display'
import { Pipeline } from './components/Pipeline'
import { EvidencePanel } from './components/EvidencePanel'
import { RiskMatrix } from './components/RiskMatrix'
import { GateCards } from './components/GateCards'
import { ResultPanel } from './components/ResultPanel'

export default function App() {
 const [state,setState]=useState<AnalysisState|null>(null); const [skill,setSkill]=useState('04'); const [evidence,setEvidence]=useState<Evidence|undefined>(); const [loading,setLoading]=useState(false); const [error,setError]=useState('');
 const risks=useMemo(()=>state?[...state.technical_risks,...state.lifecycle_risks]:[],[state]);
 async function run(){setLoading(true);setError('');try{setState(await startDemo())}catch(e){setError(e instanceof Error?e.message:'分析启动失败')}finally{setLoading(false)}}
 const showEvidence=(id:string)=>setEvidence(state?.evidence.find(item=>item.id===id));
 return <main className="app-shell"><header><div className="brand"><div className="brand-mark"><Zap size={20}/></div><div><span>PEN-X1</span><h1>产品分析师人工智能助手</h1></div></div><div className="header-meta"><span>亚马逊美国站</span><span>目标售价 34.95 美元</span><span>五种电池配置</span><b><Activity size={14}/> 演示模式</b></div><button className="start" onClick={run} disabled={loading}><Play size={16}/>{loading?'正在分析…':'开始分析 PEN-X1'}</button></header>{error&&<div className="error" role="alert">{error}</div>}<div className="workspace"><Pipeline skills={state?.skill_runs??[]} selected={skill} onSelect={setSkill}/><div className="content">{!state?<section className="hero"><span className="sample-tag">面试演示</span><h2>把产品决策拆成可追溯的智能分析流程</h2><p>点击开始分析，查看 10 个独立技能、数据来源、风险验证计划与最终决策。</p><div className="hero-cards"><article><ShieldCheck/><strong>证据优先</strong><span>事实、样例与情景假设明确分层</span></article><article><Activity/><strong>风险感知</strong><span>覆盖技术、量产与上市的生命周期扫描</span></article><article><Zap/><strong>稳定演示</strong><span>无需密钥即可完整运行的演示模式</span></article></div></section>:<><ResultPanel state={state} skillId={skill} onEvidence={showEvidence}/><RiskMatrix risks={risks.slice(0,4)} onSelect={(id)=>showEvidence(state.evidence.find(e=>id.includes('battery')&&e.id==='ev-project-brief')?.id??'ev-project-brief')}/><GateCards gates={state.decision.gates}/><section className="decision"><div><div className="section-label">最终决策</div><h2>{chinese(state.decision.decision)}</h2></div><ul>{state.decision.rationale.map(item=><li key={item}>{item}</li>)}</ul><span className={state.validation.passed?'validated':'review'}>{state.validation.passed?'校验通过':'需要复核'}</span></section></>}</div><EvidencePanel item={evidence}/></div></main>
}
