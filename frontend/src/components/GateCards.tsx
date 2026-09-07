import type { Gate } from '../types'
import { chinese } from '../display'
export function GateCards({gates}:{gates:Gate[]}) { return <section className="gates"><div className="section-label">产品关卡</div><div className="gate-grid">{gates.map(gate=><article className="gate" key={gate.name}><span className={`badge ${gate.status.toLowerCase()}`}>{chinese(gate.status)}</span><strong>{gate.name}</strong><p>{gate.reason}</p></article>)}</div></section> }
