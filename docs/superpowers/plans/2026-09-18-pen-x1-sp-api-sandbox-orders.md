# SP-API Sandbox Orders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 复用现有 Amazon 模块，以一套本地配置跑通安全、可测试的 Orders v2026-01-01 沙箱冒烟。

**Architecture:** `AmazonSettings` 读取新旧环境变量，`AmazonAuth` 缓存及刷新 LWA token，`AmazonSPAPIClient` 统一请求，独立 Orders 脚本仅调用客户端并规范化官方静态模拟订单。既有 Agent 流程不改。

**Tech Stack:** Conda `pen-x1-agent`、Python 3.11、httpx、Pydantic 2、pytest；前端只做回归构建。

**Spec:** `docs/superpowers/specs/2026-09-18-pen-x1-sp-api-sandbox-orders-design.md`

## Global Constraints

- 只修改 `D:\Projects\pen-x1-product-analyst-agent`，仅在 `feature/pen-x1-agent` 开发；不碰 main/dev、不建 venv、不用 Docker。
- 不提交 `.env`、`.env.local`、`credentials.json`、`secrets/` 或 Token；不输出敏感值。
- 不修改 Agent 技能或正式生产接入；无凭据时 Web 应用仍启动和降级。
- 开发中仅做定向测试；末尾统一完整 pytest、npm build 和真实 Sandbox 冒烟。

---

### Task 1: 配置兼容与 LWA 令牌管理

**Files:** Modify `backend/app/services/amazon_auth.py`, `.env.example`, `.gitignore`; test `backend/tests/test_amazon_sandbox_auth.py`.

**Interfaces:** `AmazonSettings.from_environment()` 首选 `SP_API_*`、兼容旧 `AMAZON_*`；`require_credentials()` 严格校验；`AmazonAuth.get_access_token(force_refresh=False)` 缓存令牌。

- [x] 写定向失败测试：缺凭据时 `require_credentials()` 报清晰安全错误，Web 的 `configured` 仍为 false；新变量覆盖旧变量；令牌到缓冲边界刷新，强制刷新只调用一次 LWA。
- [x] 运行该测试，确认失败原因是所需行为尚不存在。
- [x] 在现有 dataclass 与认证类中补齐配置、校验、可配置 token URL／timeout／buffer 与安全 `repr`；更新无敏感值样例及忽略规则。
- [x] 重跑该定向测试直至通过。

### Task 2: 通用客户端、错误模型与有界重试

**Files:** Modify `backend/app/services/amazon_sp_api_client.py`, `backend/tests/test_amazon_client.py`; add `backend/tests/test_amazon_sandbox_client.py`.

**Interfaces:** `request(method,path,params=None,json=None,headers=None,operation=None)`，保留既有 `get()`／`post()`；`AmazonAPIError.code`、`status_code`、`request_id`。

- [x] 写失败测试：用 `httpx.MockTransport` 验证 GET／POST／PUT／DELETE、401 强制刷新一次、第二次 401 停止、429 遵循 Retry-After、500 与网络故障受 `max_retries` 限制、错误消息和日志无 Token。
- [x] 运行定向测试，确认它们因尚未实现的行为失败。
- [x] 扩展现有客户端而非另建一套；例：`client.request('PUT','/test',json={'x':1})` 与 `client.request('GET','/test')` 使用同一认证与重试逻辑。禁止自定义头覆盖访问令牌。
- [x] 重跑客户端定向测试直至通过。

### Task 3: Orders 模型与独立托管沙箱冒烟

**Files:** Add `backend/app/schemas/amazon_orders.py`, `backend/app/services/amazon_orders.py`, `scripts/test_sp_api_sandbox.py`, `docs/amazon-sp-api.md`, `backend/tests/test_amazon_orders_sandbox.py`; modify `README.md`.

**Interfaces:** `AmazonOrdersSandbox.get_order()` 调用 `/orders/2026-01-01/orders/114-9876543-1234567` 并返回 `AmazonOrderSummary`；`run_smoke()` 严格校验环境，仅展示安全摘要。

- [x] 写失败测试：官方结构 `{'order': {'orderId':'114-9876543-1234567','createdTime':'2025-03-10T14:00:00Z','fulfillment':{'fulfillmentStatus':'UNSHIPPED'},'salesChannel':{'marketplaceId':'ATVPDKIKX0DER'}}}` 可规范化；缺少 `order` 不报成功；脚本对生产模式或错误 endpoint 拒绝执行。
- [x] 运行定向测试，确认失败原因是模块／行为尚不存在。
- [x] 添加薄 Orders 服务与独立脚本；`includedData` 用官方静态用例值 `RECIPIENT,PROCEEDS,FULFILLMENT`，只显示订单摘要。文档说明凭据、运行命令、沙箱与生产区别及现有 API。
- [x] 重跑定向测试直至通过。

### Task 4: FINAL VERIFICATION 与交付

- [ ] 运行完整 `pytest` 一次、`npm --prefix frontend run build` 一次；如构建改变已跟踪缓存，只恢复该生成文件。
- [ ] 核查 `.env` 与其他敏感目录不受 Git 跟踪；以不输出匹配内容的扫描检查新增源码、测试、文档与暂存差异。
- [x] 运行一次真实托管 Sandbox 冒烟：LWA 成功、Orders HTTP 200、美国站静态模拟订单 1 条。
- [ ] 只暂存本轮文件、核对分支和差异，按用户既有授权提交并推送 `origin/feature/pen-x1-agent`，不合并或强推。
