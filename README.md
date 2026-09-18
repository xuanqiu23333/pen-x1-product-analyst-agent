# PEN-X1 产品分析智能体

一个可本地演示的产品分析工作流：将内部产品事实、公开市场/竞品信息、评论样本与规则校验串联为可追溯的分析报告。

## 运行模式

- `DEMO`：完全离线。市场、竞品来自 Fixture，评论来自本地 CSV；不会调用大模型或外部网页。
- `REAL`：评论只读取项目 SQLite 中有效的 `IMPORTED_REAL` CSV 导入记录，不会使用 12 条演示评论。配置 `DEEPSEEK_API_KEY` 后进行结构化 VOC；无真实评论为 `NEED_DATA`，有评论但模型不可用为 `NEED_LLM`。品牌官网数据可继续按既有逻辑降级，但评论不降级到样例。

## 数据来源与边界

- 品牌官网：普通 HTTP/BeautifulSoup 请求、12 秒超时；只提取公开页面的标题、价格和基础规格，不使用反爬绕过或自动化浏览器。
- 亚马逊：仅限公开商品摘要（标题、价格、评分、评论数、要点）；不抓取评论页。
- 评论：DEMO 使用本地 CSV 样本；REAL 使用用户有权提供的 CSV 导入，来源类型 `IMPORTED_REAL`，不代表系统独立核验了 Amazon 平台真实性。VOC 的证据编号统一为 `ev-review-*`。
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

页面覆盖等级仅为本项目内部演示定义：0 条 `NEED_DATA`，1–49 条 `LOW_COVERAGE`，50–199 条 `PARTIAL`，200 条及以上 `SUFFICIENT_FOR_DEMO`；不是行业统计标准。真实评论 VOC 通过 DeepSeek 结构化分类和 Pydantic 校验，再由 Python 计算提及量、频率、平均评分及商品分布。每个痛点的 `ev-review-*` 可以在 Evidence 面板查看原文、商品、ASIN、评分、日期、点赞数、来源链接和采集时间。无 DeepSeek 密钥时仍可导入和查看证据，但 VOC 不会用规则分类冒充已完成。

仅导入已获得使用权限的评论文件；本项目不抓取 Amazon Review 页面，不验证导入评论是否真正来自 Amazon。

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
