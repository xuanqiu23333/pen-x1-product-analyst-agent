# SP-API Sandbox Orders 基础接入设计

## 范围

仅在既有 Amazon 认证、请求客户端上补齐可验证的 Sandbox 基础能力，并添加独立 Orders 冒烟脚本。不改 Agent 技能、同步快照、前端或正式店铺授权流程。既有 DEMO／REAL 降级行为保留。

## 配置

`SP_API_*` 为新的首选配置名；既有 `AMAZON_*` 保持兼容且仅在相应新值缺失时使用。`.env.example` 提供无凭据模板；本地 `.env` 被忽略。不会持久化短期 Access Token。只有独立冒烟命令对缺失凭据严格报错；Web 应用仍可无凭据启动并回退 Fixture。

Sandbox 命令只允许 `SP_API_ENV=sandbox`、`SP_API_REGION=na` 与 `https://sandbox.sellingpartnerapi-na.amazon.com`。默认美国 Marketplace ID。`SP_API_MAX_RETRIES=3` 解释为初次请求之外最多三次重试。

## 认证与 HTTP

复用 `backend/app/services/amazon_auth.py` 与 `amazon_sp_api_client.py`。内存缓存 LWA token 与失效时间，默认提前 300 秒刷新；401 时强制刷新后仅重放一次原请求。客户端支持 GET／POST／PUT／DELETE，自动加入令牌、日期、User-Agent；429 优先遵循合理范围内的 Retry-After，网络异常／429／5xx 有限重试。异常携带 HTTP 状态、Amazon 错误码、安全消息与 Request ID，绝不回显令牌、Client Secret 或 Refresh Token。

## Orders 沙箱验证

采用 Amazon 当前 Orders API v2026-01-01 的 `getOrder`，使用官方 OpenAPI 模型提供的美国站静态沙箱用例：订单 ID `114-9876543-1234567`，`includedData=RECIPIENT,PROCEEDS,FULFILLMENT`。响应只规范化并展示订单 ID、日期、履约状态与 Marketplace；不输出完整订单 JSON 或个人信息。脚本单独运行，不接入现有分析流程。

官方依据：[Orders API](https://developer-docs.amazon.com/sp-api/docs/orders-api)、[getOrder OpenAPI 静态沙箱用例](https://github.com/amzn/selling-partner-api-models/blob/main/models/orders-api-model/orders_2026-01-01.json)、[SP-API Sandbox](https://developer-docs.amazon.com/sp-api/docs/sp-api-sandbox)。

## 验证

以 HTTP MockTransport 完成凭据校验、令牌缓存与刷新、401 一次重放、429／500 有界重试、错误脱敏及订单规范化测试。主体完成后统一运行后端 pytest、前端构建和一次真实托管 Sandbox 冒烟。真实请求失败时保留 HTTP 状态／错误码／Request ID，不改用模拟结果冒充通过。
