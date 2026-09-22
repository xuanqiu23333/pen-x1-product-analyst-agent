# PEN-X1 Bright Data 真实评论采集设计

## 目标与边界

本轮在现有 Real Review Pipeline 上增加 Bright Data Amazon Reviews Scraper API 手动采集能力。系统读取四款 Amazon US 竞品配置，默认每款请求 100 条评论，将 API 返回的结构化数据标准化后直接写入现有 SQLite 评论库，再由 REAL 模式沿用现有 DeepSeek、Pydantic、Python 聚合、Evidence 和报告链路。

Bright Data 只承担外部采集。项目不访问 Amazon 评论 HTML，不加入 Selenium、Playwright、代理池、验证码绕过、浏览器指纹、IP 轮换、定时任务、Webhook 或后台循环。本轮不修改 VOC 的分析职责，也不生成数据补足目标数量。

## 配置与安全

`.env.example` 增加 Bright Data 数据集、单商品目标数、请求超时、轮询间隔、最大轮询时间和 `BRIGHTDATA_SCHEMA_CONFIRMED=false`。真实 `BRIGHTDATA_API_TOKEN` 只允许存在于已被 `.gitignore` 排除的 `.env`，不得进入源码、测试、文档、日志或 Git。日志和接口只暴露 `credential_configured` 布尔状态。

`data/config/amazon_competitors.json` 为四款竞品增加 `amazon_url`，保留 `brand`、`model`、`asin`、`marketplace`。系统不猜测 ASIN 或 URL；任何缺 URL 的商品标记 `PRODUCT_URL_REQUIRED` 且不触发 Bright Data 请求。缺 Token 时后端照常启动，采集接口返回 `NOT_CONFIGURED`。

## 组件职责

### BrightDataClient

`backend/app/services/brightdata_client.py` 封装认证、HTTP 超时、有限重试、异步快照轮询和下载。触发请求使用 `POST /datasets/v3/trigger`，轮询使用 `GET /datasets/v3/progress/{snapshot_id}`，状态 `starting`、`running` 继续等待，`ready` 下载，`failed` 或 `canceled` 终止。下载统一使用 Web Scraper API 的 `GET /datasets/v3/snapshot/{snapshot_id}?format=json`，不混用 Dataset Marketplace 下载接口。

`429`、`500`、`503` 最多有限重试；`401`、`403` 立即失败。轮询按配置间隔执行，累计达到最大轮询秒数后抛出 `BrightDataAPIError`，状态为 `TIMEOUT`，不得无限循环。异常仅包含 `status_code`、安全消息、`retryable` 和 `snapshot_id`，不包含 Token。

### BrightDataReviewProvider

`backend/app/data_providers/brightdata_review_provider.py` 只负责把一个或多个商品 URL 发送给 Client，并返回原始结构化评论及每个商品的采集状态。Provider 不进行 VOC、SWOT、机会或报告分析。

触发请求一次提交所有具备 URL 的竞品，每个输入包含 `url`、`max_reviews`、`variation_specific=true`、`reviews_to_not_include=[]`。默认每款 100 条，实际返回量完全以 API 结果为准。

### ReviewCollectionService

`backend/app/services/review_collection.py` 编排完整手动流程：读取竞品配置、检查 Token 和 URL、调用 Provider、按商品关联结果、标准化评论、调用 `ReviewStore.import_records()`、合并每款统计并保存 Collection Summary。服务不得把 Bright Data 数据转成临时 CSV。

`collect_all_competitor_reviews(max_reviews_per_product)` 限制参数为 1–300。HTTP API 本轮采用同步、有界轮询：前端在请求未返回时显示 `COLLECTING`，请求完成后显示 `COMPLETED`、`PARTIAL` 或 `FAILED`。不引入后台任务状态管理。

## 字段标准化与隐私

`normalize_brightdata_review()` 将版本可能变化的字段安全映射到 ReviewStore 输入：

- `review_id` 或 `id` → `external_review_id`
- `review_rating` 或 `rating` → `rating`
- `review_title` 或 `title` → `title`
- `review_text` 或 `content` → `review_text`
- `review_date` 或 `date` → `review_date`
- `verified_purchase` 或 `verified` → `verified_purchase`
- `helpful_votes` → `helpful_votes`

上述别名只用于 Mock 和首轮兼容，不被当作最终 Schema。完成 Mock 后，系统只能先采集一款竞品的五条真实评论，并在 `data/reviews_real/schema_probe/` 保存一个不含 Token、作者或个人资料值的 Schema Probe：包含实际顶层字段名、字段类型和五条记录经过白名单后的安全预览。该目录被 Git 忽略。人工检查 Probe、确认字段映射并在 `.env` 设置 `BRIGHTDATA_SCHEMA_CONFIRMED=true` 后，服务才允许超过五条或一次提交多个商品；否则返回 `SCHEMA_CONFIRMATION_REQUIRED`。因此正式四款各一百条在代码层也受硬门禁保护。

商品名、ASIN、marketplace 和输入商品 URL 由已确认的竞品配置补充；API 自身有明确业务字段时可使用，但不得臆造缺失评论内容。标准化结果继续经过现有 HTML、Unicode、空白、评分、日期、正文和 URL 校验。`author`、`reviewer_name`、`profile`、email 及其他个人信息全部丢弃。

URL 必须区分语义：Bright Data 返回的具体评论链接映射到 `review_url`，配置中的 Amazon 商品链接保存为 `product_url`。缺少具体评论链接时 `review_url=null`，不得用 `product_url` 填充或冒充评论链接。

Bright Data 评论写入时使用 `source_type=BRIGHTDATA_REAL`；CSV 评论继续使用 `IMPORTED_REAL`。两者都属于真实评论，但来源身份必须保留。

## ReviewStore 与兼容迁移

定义单一 `REAL_REVIEW_SOURCE_TYPES={"IMPORTED_REAL", "BRIGHTDATA_REAL"}`，供 `valid_reviews()`、`stats()`、判重和 REAL 模式 Provider 统一使用，避免散落硬编码。

ReviewStore 新增 `import_records(rows, source_type, source_name, ...)`。现有 `import_csv()` 保留并解析 CSV 后复用同一套标准化、校验、判重、插入和统计内部流程。判重优先使用 `external_review_id`；无稳定 ID 时使用 `asin + normalized_review_text + rating + review_date` 的 SHA-256。判重跨真实来源执行，从而同一条评论即使先从 CSV 导入、后从 Bright Data 获取，也只有一条 `VALID`，其余保留为 `DUPLICATE` 审计记录。

`review_raw` 向后兼容增加 `review_url` 与 `product_url`。现有 CSV 的 `source_url` 视为具体评论证据链接并写入 `review_url`；Bright Data 的 `product_url` 永远独立保存。保留旧列读取兼容，但新 Evidence 不再把商品页写进 `source_url`。

`review_collection_run` 向后兼容增加 `requested_reviews` 与 `failed_products`，必要时通过检查列后 `ALTER TABLE` 迁移；不删除或重建已有数据库。Bright Data 每次手动采集使用 `source=BRIGHTDATA_API`，保存目标商品、请求数、实际返回数、有效数、重复数、无效数、失败商品数、状态和时间。每款竞品的请求/返回/有效/重复/无效/状态明细以 JSON 字段随运行持久化，供最新采集接口和前端读取；迁移对旧 CSV 运行保持兼容。

## API 与状态

新增：

- `POST /api/reviews/collect`：请求体可选 `max_reviews_per_product`，默认读取配置值，限制 1–300；同步执行一次有界采集并返回 Collection Summary。
- `GET /api/reviews/collection/latest`：返回最近一次 Bright Data 采集摘要；无运行记录时根据配置返回 `NOT_CONFIGURED`、`PRODUCT_URL_REQUIRED` 或 `PENDING`，所有数字为真实数据库值或零。

状态规则：请求进行期间前端本地状态为 `COLLECTING`；所有可请求商品成功为 `COMPLETED`；至少一个成功且至少一个失败或缺 URL 为 `PARTIAL`；所有目标商品失败为 `FAILED`；缺 Token 为 `NOT_CONFIGURED`；配置商品缺 URL 为 `PRODUCT_URL_REQUIRED`。不得用目标值 400 冒充实际采集数。

## REAL 模式、VOC 与 Evidence

REAL 模式读取 `BRIGHTDATA_REAL + IMPORTED_REAL` 的 `VALID` 评论，合并后继续执行现有批处理、DeepSeek Structured Output、Pydantic 校验和 Python 聚合。真实有效评论数为零时继续返回 `NEED_DATA`；SAMPLE 永远不进入 REAL VOC。

Bright Data 评论的 Evidence 使用 `ev-review-{external_review_id}`；缺稳定 ID 时沿用内容哈希标识。Evidence 保存商品、ASIN、评分、评论日期、正文、已验证购买、点赞数、`review_url`、`product_url`、采集时间以及 `source_type=BRIGHTDATA_REAL`，使 Pain Point 可以追溯原始评论。兼容字段 `source_url` 只在 `review_url` 存在时指向具体评论链接，否则为 `null`。Provider 不参与 Evidence 或分析生成。

## 前端

现有 `RealReviewData` 保留 CSV 导入，并新增“获取真实 Amazon 评论”按钮和 Bright Data 状态。按钮触发 `POST /api/reviews/collect`，请求期间禁止重复点击并显示“采集中”。页面展示目标评论、实际获取、有效、重复、无效、最近状态，以及四款竞品各自的请求量、实际返回量、有效量和状态。所有可见状态尽量使用汉字，同时保留必要的来源标识 `BRIGHTDATA_REAL`。

页面只能展示接口返回的实际统计。Token 或 URL 缺失时显示对应配置提示，不显示虚假的完成状态或 400 条结果。

## 测试与真实验证顺序

实现采用测试优先。MockTransport 或等价 HTTP Mock 覆盖：触发成功、快照 ready、401、429 有限重试、轮询超时、畸形评论、跨来源重复、缺商品 URL、缺 Token、四款各请求 100 条，以及 REAL/SAMPLE 隔离。测试不得访问真实 Bright Data API 或消耗额度。

主体完成后统一运行后端完整 pytest、前端 build、DEMO workflow smoke 和合成 Bright Data 入库 smoke。只有 Token 与至少一个人工确认的 Amazon URL 齐全时，才执行一个商品五条真实评论 smoke，生成并人工检查 Schema Probe。确认真实 JSON key 与字段映射后显式设置 `BRIGHTDATA_SCHEMA_CONFIRMED=true`，才允许执行四商品各一百条正式采集。任何前置条件缺失时报告 `WAITING_FOR_CREDENTIALS`、`PRODUCT_URL_REQUIRED` 或 `SCHEMA_CONFIRMATION_REQUIRED`，不伪造结果。

## Git 交付

全部功能开发、提交和推送只在 `feature/pen-x1-agent` 进行。禁止切换或合并 `dev`、`main`，禁止 force push。功能提交信息为 `feat: collect real Amazon reviews via API`，真实数据库与 Token 不进入 Git。
