# Amazon SP-API Sandbox 开发说明

本轮的独立 Orders 冒烟仅支持北美托管 Sandbox。现有竞品 Catalog、Pricing、Customer Feedback 手动同步与 Agent 工作流不在本轮改造范围内，继续按既有配置降级运行。

## 本地配置

从项目的 `.env.example` 复制非敏感配置到项目根目录 `.env`，只填一套 `SP_API_*` 凭据。必填：`SP_API_LWA_CLIENT_ID`、`SP_API_LWA_CLIENT_SECRET`、`SP_API_REFRESH_TOKEN`。其他键包括 `SP_API_ENV=sandbox`、`SP_API_REGION=na`、北美 Sandbox endpoint、LWA token URL、美国／加拿大／默认 Marketplace ID、超时秒数、最大重试次数和提前刷新秒数。`SP_API_MAX_RETRIES=3` 指初次请求以外最多三次重试。Web 应用可以无凭据启动并回退 Fixture；独立冒烟脚本会在联网前给出清晰的缺凭据错误。

LWA 凭据和 refresh token 应来自获授权的 Amazon SP-API 应用及其卖家授权流程。短期 access token 由程序按需获取、缓存在内存，不填入 `.env`。获取与授权步骤见 [Amazon 官方接入文档](https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api)。凭据不得写入源码、测试、日志或 Git；已在聊天、终端或其他可共享渠道出现的凭据应轮换。

## 运行与结果

在项目根目录执行：

```powershell
C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe scripts\test_sp_api_sandbox.py
```

脚本先校验 sandbox、na、官方北美 Sandbox/LWA endpoint 和完整凭据，然后请求 LWA，再调用 Orders API v2026-01-01 的 `getOrder`。使用 [Amazon OpenAPI 模型](https://github.com/amzn/selling-partner-api-models/blob/main/models/orders-api-model/orders_2026-01-01.json)中的美国站静态用例：订单 ID `114-9876543-1234567`，`includedData=RECIPIENT,PROCEEDS,FULFILLMENT`。成功时只展示单条订单的 ID、状态、下单时间；不打印买家、地址或完整 JSON。失败时显示阶段、HTTP 状态、Amazon 错误码及请求 ID，并以非零状态退出。真实 Sandbox 与 `httpx.MockTransport` 单元测试是两件不同的验证。

托管 [Sandbox](https://developer-docs.amazon.com/sp-api/docs/sp-api-sandbox)以静态响应验证请求链路，不是正式卖家数据，也不能用来证明生产权限或吞吐量。本脚本拒绝正式 endpoint，且没有订单数据库同步或 Agent 业务接线。已有项目提供 Catalog Items、Product Pricing、Customer Feedback 的手动同步封装；Listings Items、FBA Inventory、Finances 等只是未来候选，不在本阶段开发。
