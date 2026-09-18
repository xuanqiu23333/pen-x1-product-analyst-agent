import type { Evidence } from '../types'
import { chinese } from '../display'
export function EvidencePanel({item}:{item?:Evidence}) {
  const realReview = item?.source_type === 'IMPORTED_REAL'
  return <aside className="evidence" aria-label="证据详情"><div className="section-label">证据与来源</div>{item ? <>
    <div className="evidence-id">{item.id}</div><span className="sample-tag">{chinese(item.data_nature)}</span>
    <h3>{item.source}</h3><p>{item.content}</p>
    <dl>
      {realReview && <><dt>商品</dt><dd>{item.product_name ?? '未知'}</dd><dt>ASIN</dt><dd>{item.asin ?? '未知'}</dd>
        <dt>评分</dt><dd>{item.rating ?? '未知'} / 5</dd><dt>评论日期</dt><dd>{item.review_date ?? '未知'}</dd>
        <dt>有用票数</dt><dd>{item.helpful_votes ?? 0}</dd><dt>采集时间</dt><dd>{item.collected_at ? new Date(item.collected_at).toLocaleString('zh-CN') : '未记录'}</dd></>}
      <dt>来源类型</dt><dd>{chinese(item.source_type ?? 'UNKNOWN')}</dd><dt>状态</dt><dd>{chinese(item.status)}</dd>
      <dt>可信度</dt><dd>{chinese(item.confidence)}</dd><dt>获取时间</dt><dd>{item.retrieved_at ? new Date(item.retrieved_at).toLocaleString('zh-CN') : '未记录'}</dd>
      {!realReview && <><dt>降级原因</dt><dd>{item.fallback_reason ?? '无'}</dd></>}
    </dl>
    {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">{realReview ? '查看评论来源链接' : '查看公开来源'}</a>}
    {realReview && <p className="review-note">该评论来自用户导入的 CSV，平台真实性未独立核验。</p>}
  </> : <p className="empty">点击用户痛点或在报告中引用的证据，查看原始内容。</p>}
    <div className="guard"><strong>防幻觉控制</strong><span>未知和需验证内容不会被写成确定性结论。</span></div>
  </aside>
}
