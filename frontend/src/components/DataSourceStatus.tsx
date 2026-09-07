import type { ProviderStatus } from '../types'
import { chinese } from '../display'
export function DataSourceStatus({items}:{items:Record<string,ProviderStatus>}) { return <section className="provider-status"><div className="section-label">数据源状态</div>{Object.entries(items).map(([name,item])=><article key={name}><strong>{name}</strong><span className={`badge ${item.status.toLowerCase()}`}>{chinese(item.status)}</span><small>{chinese(item.source_type)}{item.fallback_reason ? ` · 已降级：${item.fallback_reason}` : ''}</small></article>)}</section> }
