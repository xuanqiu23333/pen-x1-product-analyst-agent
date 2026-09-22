# PEN-X1 产品分析智能体

一个可本地演示的产品分析工作流：将内部产品事实、公开市场/竞品信息、评论样本与规则校验串联为可追溯的分析报告。

## 运行模式

- `DEMO`：完全离线。市场、竞品来自 Fixture，评论来自本地 CSV；不会调用大模型或外部网页。
- `REAL`：评论只读取项目 SQLite 中有效的 `IMPORTED_REAL`、`BRIGHTDATA_REAL` 或 `APIFY_REAL` 记录，不会使用 12 条演示评论。配置 `DEEPSEEK_API_KEY` 后进行结构化 VOC；无真实评论为 `NEED_DATA`，有评论但模型不可用为 `NEED_LLM`。品牌官网数据可继续按既有逻辑降级，但评论不降级到样例。

## 数据来源与边界

- 品牌官网：普通 HTTP/BeautifulSoup 请求、12 秒超时；只提取公开页面的标题、价格和基础规格，不使用反爬绕过或自动化浏览器。
- 亚马逊商品数据：SP-API 仅同步官方接口可用的目录、价格和 Customer Feedback 聚合主题；不抓取评论页。
- 评论：DEMO 使用本地 CSV 样本；REAL 使用用户有权提供的 CSV（`IMPORTED_REAL`），或由 Bright Data（`BRIGHTDATA_REAL`）/Apify（`APIFY_REAL`）返回的 Amazon 评论数据。三种真实来源共用清洗、跨来源去重、SQLite、VOC 和 Evidence 链路，且不会混入 SAMPLE。VOC 的证据编号统一为 `ev-review-*`。
- 每条证据可附来源类型、链接、获取时间、可用状态和降级原因；市场样本/演示资料会让 Market Gate 处于“部分通过”，不会冒充真实结论。

## 验证

```powershell
C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend\tests -v --basetemp backend\.pytest-tmp
npm --prefix frontend run build
```

产物目录 `data/outputs/` 与测试临时目录 `backend/.pytest-tmp/` 均已忽略，不会进入版本库。

## 真实评论 CSV 导入

在页面“真实评论数据”区选择 UTF-8 CSV 并点击“导入真实评论”，或把 CSV 原始字节作为 `text/csv` 请求体发送到 `POST /api/reviews/import`。文件上限 5 MB，表头须包含：

```text
review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url
```

`review_id` 可留空；`asin` 为 10 位字母数字；`rating` 为 1–5；`review_text`、`product` 和日期必填。日期支持 `YYYY-MM-DD`、`MM/DD/YYYY`、`YYYY/MM/DD`、`Mar 10, 2025`；`verified` 接受 yes/no、true/false、1/0；`helpful` 是非负整数。HTML、Unicode 和空白会被标准化，非法行不会进入 VOC。多余的 reviewer 姓名、电邮等列会被丢弃，不存入数据库。

导入运行与评论分别存于本项目 `data/reviews_real/reviews.sqlite3` 中的 `review_collection_run`、`review_raw` 两表。有效、重复、无效行有独立状态；优先按外部评论 ID 去重，缺 ID 时按 ASIN、清洗后正文、评分和日期的 SHA-256 去重。SQLite 文件已在 `.gitignore` 排除。`GET /api/reviews/stats` 返回累计原始/有效/重复/无效数量、四竞品分布、来源占比与最近采集时间。

页面覆盖等级仅为本项目内部演示定义：0 条 `NEED_DATA`，1–19 条 `LOW_COVERAGE`，20–49 条 `PARTIAL`，50 条及以上 `GOOD_COVERAGE`；不是行业统计标准。真实评论 VOC 通过 DeepSeek 结构化分类和 Pydantic 校验，再由 Python 计算提及量、频率、平均评分及商品分布。每个痛点的 `ev-review-*` 可以在 Evidence 面板查看原文、商品、ASIN、评分、日期、点赞数、来源链接和采集时间。无 DeepSeek 密钥时仍可导入和查看证据，但 VOC 不会用规则分类冒充已完成。

仅导入已获得使用权限的评论文件；本项目自身不抓取 Amazon Review 页面，不验证 CSV 评论是否真正来自 Amazon。

## Bright Data 真实评论采集

本项目通过 Bright Data Amazon Reviews Scraper API 采集，不实现 Amazon 页面爬虫、代理池、验证码绕过或浏览器自动化。调用链固定为：

```text
POST /datasets/v3/trigger
GET  /datasets/v3/progress/{snapshot_id}
GET  /datasets/v3/snapshot/{snapshot_id}?format=json
```

1. 只在未跟踪的 `.env` 中填写 `BRIGHTDATA_API_TOKEN`，其余参数参考 `.env.example`。Token 不写日志、不写响应、不保存到 SQLite。
2. 在 `data/config/amazon_competitors.json` 中为已确认的竞品填写真实 `amazon_url`；项目不会猜 URL。URL 缺失时返回 `PRODUCT_URL_REQUIRED`，无 Token 时返回 `NOT_CONFIGURED`，均不会影响 DEMO 模式。
3. 首次必须保持 `BRIGHTDATA_SCHEMA_CONFIRMED=false`，只配置一款商品并调用 `POST /api/reviews/collect`，请求 `{"max_reviews_per_product": 5}`。系统会在已忽略的 `data/reviews_real/schema_probe/` 保存实际键名、类型和不含标题/正文/作者信息的安全预览。
4. 人工核对 5 条响应的真实字段映射后，才可将 `BRIGHTDATA_SCHEMA_CONFIRMED=true`，再执行四款商品每款最多 100 条。未确认 Schema 时，服务端会拒绝多商品或每款超过 5 条的请求。

采集进度和结果按真实数量展示 Requested、Collected、Valid、Duplicate、Invalid 和各竞品明细；目标 400 不等于成功 400。`GET /api/reviews/collection/latest` 只读取最近结果，不发起外部请求。跨 `IMPORTED_REAL` 与 `BRIGHTDATA_REAL` 按外部 Review ID 或内容哈希统一去重。

Evidence 明确区分 `review_url` 与 `product_url`：只有具体评论链接可以作为原始评论来源；商品链接不会冒充评论链接。Bright Data 返回字段变化时，应重新执行 1×5 Schema Probe，而不是猜测字段。真实评论为 0 时，REAL 模式 VOC 保持 `NEED_DATA`。

## Apify 真实评论采集

默认真实采集 Provider 可通过 `REVIEW_COLLECTION_PROVIDER=APIFY` 启用，Bright Data 实现继续保留为备用。免费模式使用 `kestrel/amazon-reviews-scraper` Actor；`axesso_data/amazon-reviews-scraper` 仅保留为历史兼容配置，不在免费模式启用。轮询只接受 `READY/RUNNING/SUCCEEDED/FAILED/TIMED-OUT/ABORTED`，达到 `APIFY_MAX_POLL_SECONDS` 后终止等待，不会无限轮询。Kestrel 单商品请求会将 `maxReviewsPerProduct` 限制为最多 13，并过滤 Dataset 的 `status` 行，只把 `type=review` 交给 ReviewStore。

Token 只写入未跟踪的 `.env` 中的 `APIFY_API_TOKEN`。未配置时接口返回 `APIFY_NOT_CONFIGURED`，应用仍可正常运行。Actor 成功返回的最多 5 条脱敏 Schema 样本保存在 `data/fixtures/apify_review_response.sample.json`；样本排除用户名、用户 ID、作者和 Profile 字段。Apify、Bright Data 与 CSV 按 Review ID 或内容哈希跨来源去重。

## Amazon SP-API 手动同步

1. 在项目自己的 `.env` 中填写 `.env.example` 所列的 `SP_API_LWA_CLIENT_ID`、`SP_API_LWA_CLIENT_SECRET`、`SP_API_REFRESH_TOKEN`；该文件已被 Git 忽略。既有 `AMAZON_*` 配置名仍被兼容读取，但请勿在一个 `.env` 中重复填写两套凭据。配置应用需要 Amazon 授予相应 Catalog、Pricing 和 Customer Feedback 操作权限。
2. 在 `data/config/amazon_competitors.json` 中核实四款竞品的真实子 ASIN 后手动填写。当前四项为空；项目不会猜测 ASIN。
3. 先保持 `SP_API_ENV=sandbox`。点击页面的“同步亚马逊数据”，或调用 `POST /api/amazon/sync`。沙箱只提供模拟响应；页面不会把它标记为真实商品数据。
4. 既有正式只读流程仍保留，需具备相应权限后单独配置 `SP_API_ENV=production`、正式 endpoint 与 `AMAZON_REAL_DATA_ENABLED=true`。本轮独立 Orders 冒烟脚本强制 Sandbox，绝不会走该流程。DEMO 模式始终离线。

同步状态与记录可通过 `GET /api/amazon/sync/latest`、`GET /api/amazon/products`、`GET /api/amazon/products/{asin}` 和 `GET /api/amazon/products/{asin}/feedback` 查询。摘要直接统计目标商品、完整成功商品、目录记录、价格记录、官方反馈主题、实际 API 请求、错误与限流事件。无凭证返回 `NOT_CONFIGURED`；ASIN 为空返回 `ASIN_REQUIRED`；失败商品继续使用官网或 Fixture。

快照保存在 `data/amazon/latest/snapshot.json` 与 `data/amazon/history/YYYY-MM-DD/<run-id>.json`；这两个目录及真实同步数据均不提交 Git。快照仅保存标准化商品记录与 Fact/Evidence，不保存 Token、Secret 或原始响应。官方 Customer Feedback 是主题、提及量和趋势，不是评论全文；CSV 中的原始评论数量始终单独展示。第二阶段调度器与变化触发尚未加入，待真实手动链路通过后实施。

接口依据：[Amazon SP-API 连接与请求头](https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api)、[Catalog Items](https://developer-docs.amazon.com/sp-api/reference/getcatalogitem)、[Product Pricing getItemOffers](https://developer-docs.amazon.com/sp-api/reference/getitemoffers)、[Customer Feedback topics](https://developer-docs.amazon.com/sp-api/reference/getitemreviewtopics)、[Amazon 沙箱](https://developer-docs.amazon.com/sp-api/docs/sp-api-sandbox)。

## Orders Sandbox 独立冒烟

该脚本只验证 LWA → 北美 Sandbox → Orders v2026-01-01 静态模拟订单，不修改 Agent 或同步快照。先配置项目本地 `.env`，再使用 Conda `pen-x1-agent` 的 Python 运行：

```powershell
C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe scripts\test_sp_api_sandbox.py
```

脚本仅显示订单摘要和脱敏错误；详细配置、官方静态测试用例与局限见 [Amazon SP-API 开发说明](docs/amazon-sp-api.md)。
