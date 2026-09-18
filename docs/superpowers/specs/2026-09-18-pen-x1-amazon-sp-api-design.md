# PEN-X1 Amazon SP-API 手动同步设计

用户已给定第三轮增量需求及验收条件。本轮只实现第一阶段手动同步；调度、变化检测和增量重跑在真实凭证与 ASIN 完成端到端验证之后再实施。

## 数据流

前端按钮或 `POST /api/amazon/sync` → 配置与 ASIN 检查 → LWA 缓存令牌 → Catalog v2022-04-01 → Pricing v0 `getItemOffers` → Customer Feedback v2024-06-01 topics/trends → 标准化记录 → Fact/Evidence → 忽略的本地快照。REAL 分析读取最新生产快照；DEMO 始终离线使用 Fixture/CSV。

官方 Customer Feedback 返回前十正面和负面主题及六个月趋势，不提供原始评论全集；CSV 评论数量与官方 topic mentions 分开统计。沙箱响应标记 `SANDBOX`，不得提升为真实市场证据。无凭证或无 ASIN 返回显式状态且不触发外部请求。

## 边界

`amazon_auth` 管理 LWA 令牌；`amazon_sp_api_client` 管理请求头、有限重试、限流头和安全错误；`amazon_sp_api_provider` 调用四个只读操作并标准化；`amazon_sync` 逐个产品部分成功、计数和保存；现有 Runner、竞品、VOC、机会、决策及报告仅消费标准化 Fact/Evidence/竞品行。前端只增加一块同步状态区。

## 安全与验证

令牌及密钥只在内存和请求中使用，不持久化、不输出；快照仅存标准化结果。测试使用注入 HTTP 传输验证请求契约和错误分支，最后集中运行全量 pytest、前端构建、DEMO、沙箱冒烟。当前无凭证与 ASIN，真实沙箱/生产网络冒烟只能报告未执行，不得伪称成功。
