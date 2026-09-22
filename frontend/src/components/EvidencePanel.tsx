import type { Evidence } from '../types'
import { chinese } from '../display'
export function EvidencePanel({item}:{item?:Evidence}) {
  const realReview = ['IMPORTED_REAL', 'BRIGHTDATA_REAL', 'APIFY_REAL'].includes(item?.source_type ?? '')
  return <aside className="evidence" aria-label="证据详情"><div className="section-label">证据与来源</div>{item ? <>
    <div className="evidence-id">{item.id}</div><span className="sample-tag">{chinese(item.data_nature)}</span>
    <h3>{item.source}</h3><p>{item.content}</p>
    <dl>
      {realReview && <><dt>商品</dt><dd>{item.product_name ?? '未知'}</dd><dt>ASIN</dt><dd>{item.asin ?? '未知'}</dd>
        <dt>评分</dt><dd>{item.rating ?? '未知'} / 5</dd><dt>评论标题</dt><dd>{item.review_title || '原始数据未提供'}</dd><dt>评论日期</dt><dd>{item.review_date ?? '未知'}</dd>
        <dt>已验证购买</dt><dd>{item.verified_purchase === true ? '是' : item.verified_purchase === false ? '否' : '未知'}</dd>
        <dt>有用票数</dt><dd>{item.helpful_votes ?? 0}</dd><dt>采集时间</dt><dd>{item.collected_at ? new Date(item.collected_at).toLocaleString('zh-CN') : '未记录'}</dd></>}
      <dt>来源类型</dt><dd>{chinese(item.source_type ?? 'UNKNOWN')}</dd><dt>状态</dt><dd>{chinese(item.status)}</dd>
      <dt>可信度</dt><dd>{chinese(item.confidence)}</dd><dt>获取时间</dt><dd>{item.retrieved_at ? new Date(item.retrieved_at).toLocaleString('zh-CN') : '未记录'}</dd>
      {!realReview && <><dt>降级原因</dt><dd>{item.fallback_reason ?? '无'}</dd></>}
    </dl>
    <div className="evidence-links">
      {realReview && item.review_url && <a href={item.review_url} target="_blank" rel="noreferrer">查看原始评论</a>}
      {realReview && item.product_url && <a href={item.product_url} target="_blank" rel="noreferrer">查看商品页面</a>}
      {!realReview && item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">查看公开来源</a>}
    </div>
    {item?.source_type === 'IMPORTED_REAL' && <p className="review-note">该评论来自用户导入的 CSV，平台真实性未独立核验。</p>}
    {item?.source_type === 'BRIGHTDATA_REAL' && <p className="review-note">该评论由 Bright Data API 采集；商品链接与具体评论链接分别展示。</p>}
    {item?.source_type === 'APIFY_REAL' && <p className="review-note">该评论由 Apify API 采集；不展示评论者姓名、主页或用户标识。</p>}
  </> : <p className="empty">点击用户痛点或在报告中引用的证据，查看原始内容。</p>}
    <div className="guard"><strong>防幻觉控制</strong><span>未知和需验证内容不会被写成确定性结论。</span></div>
  </aside>
}
