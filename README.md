# PEN-X1 产品分析智能体

一个可本地演示的产品分析工作流：将内部产品事实、公开市场/竞品信息、评论样本与规则校验串联为可追溯的分析报告。

## 运行模式

- `DEMO`：完全离线。市场、竞品来自 Fixture，评论来自本地 CSV；不会调用大模型或外部网页。
- `REAL`：在配置 `DEEPSEEK_API_KEY` 后复用同一个 DeepSeek Provider，供 VOC、机会、技术风险、生命周期风险、决策、报告六个核心技能调用。品牌官网仅作普通公开页面请求；失败后显示“已降级”并回退到演示资料。

## 数据来源与边界

- 品牌官网：普通 HTTP/BeautifulSoup 请求、12 秒超时；只提取公开页面的标题、价格和基础规格，不使用反爬绕过或自动化浏览器。
- 亚马逊：仅限公开商品摘要（标题、价格、评分、评论数、要点）；不抓取评论页。
- 评论：DEMO 使用本地 CSV 样本；REAL 可接入合规导入的评论数据。VOC 的证据编号统一为 `ev-review-*`。
- 每条证据可附来源类型、链接、获取时间、可用状态和降级原因；市场样本/演示资料会让 Market Gate 处于“部分通过”，不会冒充真实结论。

## 验证

```powershell
C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend\tests -v --basetemp backend\.pytest-tmp
npm --prefix frontend run build
```

产物目录 `data/outputs/` 与测试临时目录 `backend/.pytest-tmp/` 均已忽略，不会进入版本库。

## Amazon SP-API 手动同步

1. 在项目自己的 `.env` 中填写 `.env.example` 所列的 LWA Client ID、Client Secret、Refresh Token；该文件已被 Git 忽略。配置应用需要 Amazon 授予相应 Catalog、Pricing 和 Customer Feedback 操作权限。
2. 在 `data/config/amazon_competitors.json` 中核实四款竞品的真实子 ASIN 后手动填写。当前四项为空；项目不会猜测 ASIN。
3. 先保持 `AMAZON_SP_API_MODE=sandbox`。点击页面的“同步亚马逊数据”，或调用 `POST /api/amazon/sync`。沙箱只提供模拟响应；页面不会把它标记为真实商品数据。
4. 具备正式只读权限后，将模式改为 `production` 并将 `AMAZON_REAL_DATA_ENABLED=true`，重启后端再手动同步。随后通过 `POST /api/analysis-runs`、请求体 `{"mode":"REAL"}` 启动读取最新生产快照的现有分析工作流。DEMO 模式始终离线。

同步状态与记录可通过 `GET /api/amazon/sync/latest`、`GET /api/amazon/products`、`GET /api/amazon/products/{asin}` 和 `GET /api/amazon/products/{asin}/feedback` 查询。摘要直接统计目标商品、完整成功商品、目录记录、价格记录、官方反馈主题、实际 API 请求、错误与限流事件。无凭证返回 `NOT_CONFIGURED`；ASIN 为空返回 `ASIN_REQUIRED`；失败商品继续使用官网或 Fixture。

快照保存在 `data/amazon/latest/snapshot.json` 与 `data/amazon/history/YYYY-MM-DD/<run-id>.json`；这两个目录及真实同步数据均不提交 Git。快照仅保存标准化商品记录与 Fact/Evidence，不保存 Token、Secret 或原始响应。官方 Customer Feedback 是主题、提及量和趋势，不是评论全文；CSV 中的原始评论数量始终单独展示。第二阶段调度器与变化触发尚未加入，待真实手动链路通过后实施。

接口依据：[Amazon SP-API 连接与请求头](https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api)、[Catalog Items](https://developer-docs.amazon.com/sp-api/reference/getcatalogitem)、[Product Pricing getItemOffers](https://developer-docs.amazon.com/sp-api/reference/getitemoffers)、[Customer Feedback topics](https://developer-docs.amazon.com/sp-api/reference/getitemreviewtopics)、[Amazon 沙箱](https://developer-docs.amazon.com/sp-api/docs/sp-api-sandbox)。
