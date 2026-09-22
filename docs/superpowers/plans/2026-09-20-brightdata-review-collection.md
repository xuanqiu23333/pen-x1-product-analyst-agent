# Bright Data Real Review Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入 Bright Data Amazon Reviews Scraper API，将四款竞品的真实评论安全写入现有 Real Review Pipeline，并让 REAL 模式继续通过 DeepSeek、Pydantic、Python 聚合和 Evidence 使用这些评论。

**Architecture:** `BrightDataClient` 封装 Web Scraper v3 trigger/progress/snapshot 链路，`BrightDataReviewProvider` 只采集原始结构化数据，`ReviewCollectionService` 读取竞品配置、执行 Schema Probe 门禁、标准化并调用 `ReviewStore.import_records()`。SQLite 以兼容迁移扩展采集统计及 `review_url`/`product_url`，API 和现有 `RealReviewData` 只展示数据库中的真实数量。

**Tech Stack:** Python 3.11、FastAPI、httpx、SQLite、Pydantic 2、pytest、React 18、TypeScript、Vite。

**Spec:** `docs/superpowers/specs/2026-09-20-brightdata-review-collection-design.md`

## Global Constraints

- 只在 `D:\Projects\pen-x1-product-analyst-agent` 的 `feature/pen-x1-agent` 分支开发；禁止切换或合并 `dev`/`main`，禁止 force push。
- 使用 Conda `pen-x1-agent` 与 Python 3.11；禁止 Docker、venv、Redis、PostgreSQL、Kafka、Celery、Scheduler 和系统配置修改。
- 不开发 Amazon HTML 爬虫、Selenium、Playwright、代理池、验证码绕过、浏览器指纹或 IP 轮换。
- `BRIGHTDATA_API_TOKEN` 只允许存在于 `.env`；测试、代码、README、日志和 Git 不得出现真实 Token。
- SAMPLE 不得进入 REAL VOC；真实评论为零时保持 `NEED_DATA`。
- 真实调用顺序固定为 Mock → 一款商品五条 → 检查并确认 Schema → 四款各一百条；未确认 Schema 时代码必须拒绝大批量采集。
- 所有可见界面内容尽量使用汉字；`BRIGHTDATA_REAL` 等必要来源标识保留。
- 主体完成前只运行定向测试；最后统一运行完整 pytest、前端 build、DEMO smoke 和受条件保护的真实 smoke。
- 最终功能提交信息固定为 `feat: collect real Amazon reviews via API`，只推送 `origin/feature/pen-x1-agent`。

## Review Focus

- Bright Data 返回 JSON 对象包装而不是直接数组时，应只接受明确的 `data`/`results` 数组，其他形状安全失败且不写库。
- 评论 ID 在 CSV 与 Bright Data 之间重复时，只保留一条 `VALID`，第二条保存为 `DUPLICATE`。
- 旧 SQLite 缺新增列时，首次连接应原地迁移并保留已有 CSV 评论和运行记录。
- Bright Data 仅返回商品 URL、没有具体评论 URL 时，Evidence 的 `review_url` 与兼容 `source_url` 必须为空，`product_url` 保留商品链接。
- 未确认 Schema 时，即使调用方请求多商品或每商品超过五条，也应返回 `SCHEMA_CONFIRMATION_REQUIRED` 且不调用 Bright Data。

---

### Task 1: 扩展评论标准化与 ReviewStore

**Files:**
- Modify: `backend/app/services/review_cleaning.py`
- Modify: `backend/app/services/review_store.py`
- Modify: `backend/app/data_providers/review_csv_provider.py`
- Test: `backend/tests/test_review_import.py`
- Create: `backend/tests/test_brightdata_review_store.py`

**Interfaces:**
- Produces: `REAL_REVIEW_SOURCE_TYPES: frozenset[str]`
- Produces: `normalize_review_record(row: dict, source_type: str) -> tuple[dict, bool]`
- Produces: `normalize_brightdata_review(raw: dict, competitor: dict) -> tuple[dict, bool]`
- Produces: `ReviewStore.import_records(rows: list[dict], source_type: str, source_name: str, *, requested_reviews: int = 0, target_products: int | None = None, failed_products: int = 0, status: str | None = None, product_summaries: list[dict] | None = None, snapshot_id: str | None = None) -> dict`
- Produces: `ReviewStore.latest_collection(source: str = "BRIGHTDATA_API") -> dict | None`
- Preserves: `ReviewStore.import_csv(csv_text: str) -> dict`

- [ ] **Step 1: 写 ReviewStore 迁移与跨来源判重失败测试**

在 `test_brightdata_review_store.py` 写测试，先构造旧版数据库，再初始化 `ReviewStore`：

```python
def test_old_database_migrates_without_losing_imported_reviews(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite3")
    store.import_csv(CSV_WITH_ONE_VALID_REVIEW)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("ALTER TABLE review_collection_run RENAME TO old_run")
        # 测试辅助函数按旧 schema 恢复表和已有行
    migrated = ReviewStore(store.db_path)
    assert migrated.valid_reviews()[0]["review_id"] == "R1"
    assert {"requested_reviews", "failed_products", "product_summaries_json", "snapshot_id"} <= run_columns(store.db_path)
    assert {"review_url", "product_url"} <= review_columns(store.db_path)

def test_duplicate_is_detected_across_csv_and_brightdata(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite3")
    store.import_csv(CSV_WITH_R1)
    result = store.import_records([CANONICAL_R1], "BRIGHTDATA_REAL", "Bright Data API")
    assert result["valid_reviews"] == 0
    assert result["duplicate_reviews"] == 1
    assert len(store.valid_reviews()) == 1
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_brightdata_review_store.py -v --basetemp backend/.pytest-tmp/store-red -p no:cacheprovider`

Expected: FAIL，原因是 `import_records`、真实来源集合和新增列尚不存在。

- [ ] **Step 3: 实现单一标准化与兼容迁移**

在 `review_cleaning.py` 中让 CSV 和 Bright Data 都先转为下列 canonical 输入，再复用相同清洗：

```python
REAL_REVIEW_SOURCE_TYPES = frozenset({"IMPORTED_REAL", "BRIGHTDATA_REAL"})

def normalize_brightdata_review(raw: dict, competitor: dict) -> tuple[dict, bool]:
    canonical = {
        "review_id": raw.get("review_id") or raw.get("id"),
        "asin": raw.get("asin") or competitor.get("asin"),
        "product": raw.get("product_name") or raw.get("product") or f"{competitor['brand']} {competitor['model']}",
        "rating": raw.get("review_rating") if raw.get("review_rating") is not None else raw.get("rating"),
        "title": raw.get("review_title") or raw.get("title"),
        "review_text": raw.get("review_text") or raw.get("content"),
        "date": raw.get("review_date") or raw.get("date"),
        "verified": raw.get("verified_purchase") if raw.get("verified_purchase") is not None else raw.get("verified"),
        "helpful": raw.get("helpful_votes", 0),
        "review_url": raw.get("review_url"),
        "product_url": competitor.get("amazon_url"),
        "marketplace": competitor.get("marketplace", "US"),
    }
    return normalize_review_record(canonical, "BRIGHTDATA_REAL")
```

`_connect()` 使用 `PRAGMA table_info` 检查列并分别执行固定的 `ALTER TABLE ... ADD COLUMN`，禁止根据外部输入拼接列名。新增列：

```sql
review_collection_run.requested_reviews INTEGER NOT NULL DEFAULT 0
review_collection_run.failed_products INTEGER NOT NULL DEFAULT 0
review_collection_run.product_summaries_json TEXT NOT NULL DEFAULT '[]'
review_collection_run.snapshot_id TEXT
review_raw.review_url TEXT
review_raw.product_url TEXT
```

判重 SQL 使用 `source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL')`，不再限定同一来源。CSV 的 `source_url` 映射到 `review_url`；`source_url` 兼容值只能等于具体评论链接。

- [ ] **Step 4: 让 `import_csv()` 复用 `import_records()`**

`import_csv()` 只保留文件大小、表头和 CSV 解析，随后调用：

```python
return self.import_records(
    list(reader),
    source_type="IMPORTED_REAL",
    source_name="CSV_IMPORT",
)
```

`valid_reviews()` 和 `stats()` 统一读取两种真实来源，并保留每行原始 `source_type`、`review_url`、`product_url`。ProviderResult 的来源汇总改为 `REAL_REVIEW`，行级来源保持不变。

- [ ] **Step 5: 运行定向测试确认 GREEN**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_review_import.py backend/tests/test_brightdata_review_store.py -v --basetemp backend/.pytest-tmp/store-green -p no:cacheprovider`

Expected: PASS；原 CSV 测试不回归，新增迁移、跨来源判重、URL 区分测试通过。

### Task 2: 实现 Bright Data Web Scraper v3 客户端

**Files:**
- Create: `backend/app/services/brightdata_client.py`
- Create: `backend/tests/test_brightdata_client.py`

**Interfaces:**
- Produces: `BrightDataSettings.from_environment() -> BrightDataSettings`
- Produces: `BrightDataAPIError(status_code: int | None, message: str, retryable: bool, snapshot_id: str | None = None)`
- Produces: `BrightDataClient.trigger_collection(inputs: list[dict]) -> str`
- Produces: `BrightDataClient.get_snapshot_status(snapshot_id: str) -> dict`
- Produces: `BrightDataClient.download_snapshot(snapshot_id: str) -> list[dict]`
- Produces: `BrightDataClient.collect(inputs: list[dict]) -> tuple[str, list[dict]]`

- [ ] **Step 1: 写 trigger/progress/snapshot 失败测试**

使用 `httpx.MockTransport` 检查完整请求，不使用真实网络：

```python
def test_collect_uses_web_scraper_v3_snapshot_endpoint():
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path, request.url.params))
        if request.url.path.endswith("/trigger"):
            return httpx.Response(200, json={"snapshot_id": "s_test"})
        if request.url.path.endswith("/progress/s_test"):
            return httpx.Response(200, json={"status": "ready"})
        return httpx.Response(200, json=[{"review_id": "R1"}])
    snapshot_id, rows = client_for(handler).collect([{"url": PRODUCT_URL}])
    assert snapshot_id == "s_test"
    assert rows == [{"review_id": "R1"}]
    assert seen[-1][1] == "/datasets/v3/snapshot/s_test"
    assert seen[-1][2]["format"] == "json"
```

分别增加 401/403 不重试、429/500/503 最多配置次数、状态 `failed`/`canceled`、轮询超时、缺 `snapshot_id`、非法下载形状测试。注入 `sleep=lambda _: None` 与可控 monotonic clock，避免测试真实等待。

- [ ] **Step 2: 运行测试确认 RED**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_brightdata_client.py -v --basetemp backend/.pytest-tmp/client-red -p no:cacheprovider`

Expected: FAIL with `ModuleNotFoundError: app.services.brightdata_client`。

- [ ] **Step 3: 实现设置、异常、有限重试与有界轮询**

设置默认值严格为：dataset `gd_le8e811kzy4ggddlq`、target 100、timeout 60、poll 5、max poll 180、max retries 3、schema confirmed false。Client 构造器接受测试注入：

```python
class BrightDataClient:
    BASE_URL = "https://api.brightdata.com"

    def __init__(self, settings, http_client=None, sleep=time.sleep, monotonic=time.monotonic): ...
```

所有请求头只构造 `Authorization: Bearer ...`，错误消息从安全的 HTTP 状态和 API `error`/`message` 字段归一化；异常 `repr` 与 `str` 不包含 header 或 Token。`collect()` 只在 progress 为 `ready` 时下载 `/datasets/v3/snapshot/{id}?format=json`。

- [ ] **Step 4: 运行定向测试确认 GREEN**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_brightdata_client.py -v --basetemp backend/.pytest-tmp/client-green -p no:cacheprovider`

Expected: PASS；MockTransport 请求次数和路径断言全部通过。

### Task 3: Provider、Schema Probe 与采集编排

**Files:**
- Create: `backend/app/data_providers/brightdata_review_provider.py`
- Create: `backend/app/services/review_collection.py`
- Modify: `data/config/amazon_competitors.json`
- Modify: `.env.example`
- Test: `backend/tests/test_brightdata_provider.py`
- Test: `backend/tests/test_review_collection.py`

**Interfaces:**
- Consumes: `BrightDataClient.collect(inputs) -> (snapshot_id, rows)`
- Consumes: `ReviewStore.import_records(...) -> dict`
- Produces: `BrightDataReviewProvider.collect_product_reviews(...) -> list[dict]`
- Produces: `BrightDataReviewProvider.collect_competitors(...) -> dict`
- Produces: `ReviewCollectionService.collect_all_competitor_reviews(max_reviews_per_product: int | None = None) -> dict`
- Produces: `ReviewCollectionService.latest_collection() -> dict`

- [ ] **Step 1: 写 Provider 批量输入与服务配置失败测试**

```python
def test_four_products_request_one_hundred_each(fake_client, competitors):
    result = BrightDataReviewProvider(fake_client).collect_competitors(competitors, 100)
    assert len(fake_client.inputs) == 4
    assert all(item["max_reviews"] == 100 for item in fake_client.inputs)
    assert all(item["variation_specific"] is True for item in fake_client.inputs)

def test_missing_token_returns_not_configured_without_calling_provider(tmp_path):
    service = service_with(token="", competitors=FOUR_CONFIGURED_PRODUCTS)
    assert service.collect_all_competitor_reviews()["status"] == "NOT_CONFIGURED"
    assert provider.call_count == 0

def test_unconfirmed_schema_blocks_large_collection(tmp_path):
    service = service_with(token="test-token", schema_confirmed=False, competitors=FOUR_CONFIGURED_PRODUCTS)
    result = service.collect_all_competitor_reviews(100)
    assert result["status"] == "SCHEMA_CONFIRMATION_REQUIRED"
    assert provider.call_count == 0
```

增加：URL 缺失时 `PRODUCT_URL_REQUIRED`、一款五条允许采集并生成 Probe、畸形评论记 INVALID、多商品部分失败记 PARTIAL、真实返回数量不补齐目标、每商品统计按 URL/ASIN 归属。

- [ ] **Step 2: 运行测试确认 RED**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_brightdata_provider.py backend/tests/test_review_collection.py -v --basetemp backend/.pytest-tmp/collection-red -p no:cacheprovider`

Expected: FAIL，Provider 和 Service 模块尚不存在。

- [ ] **Step 3: 实现 Provider 与安全 Schema Probe**

Provider 一次传入全部可采集商品。Service 使用输入 URL 与响应的 `url`/`product_url`/`asin` 做明确归属；无法归属的记录标为 INVALID，不随意分配商品。

Probe 文件只保存：

```json
{
  "snapshot_id": "s_xxx",
  "observed_at": "ISO-8601",
  "record_count": 5,
  "fields": {"review_id": ["str"], "review_rating": ["int"]},
  "safe_previews": [{"external_review_id": "R1", "rating": 5, "review_url": "https://..."}]
}
```

`safe_previews` 必须从 canonical 白名单构造，不序列化原始对象，不含 `author`、`reviewer_name`、`profile`、email 或 Token。Probe 路径位于已经被 `data/reviews_real/` 规则忽略的目录。

- [ ] **Step 4: 实现 Collection Summary 和状态规则**

Service 先验证 `1 <= max_reviews_per_product <= 300`。状态判定：缺 Token=`NOT_CONFIGURED`；无可采集 URL=`PRODUCT_URL_REQUIRED`；未确认且请求大于五条或多于一商品=`SCHEMA_CONFIRMATION_REQUIRED`；全部成功=`COMPLETED`；有成功也有失败/缺 URL=`PARTIAL`；全部请求失败=`FAILED`。传给 Store 的 `requested_reviews` 是实际准备请求的商品数乘目标值，`collected_reviews` 是 API 实际返回记录数。

- [ ] **Step 5: 运行定向测试确认 GREEN**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_brightdata_provider.py backend/tests/test_review_collection.py backend/tests/test_brightdata_review_store.py -v --basetemp backend/.pytest-tmp/collection-green -p no:cacheprovider`

Expected: PASS；不会访问真实 API。

### Task 4: 暴露采集 API 并保持后端可启动

**Files:**
- Modify: `backend/app/api/routes.py`
- Modify: `backend/tests/test_review_api.py`

**Interfaces:**
- Produces: `POST /api/reviews/collect`
- Produces: `GET /api/reviews/collection/latest`
- Produces: `ReviewCollectRequest(max_reviews_per_product: int = Field(default=100, ge=1, le=300))`

- [ ] **Step 1: 写 API 失败测试**

使用 FastAPI dependency override 注入假的 Collection Service：

```python
def test_collect_endpoint_forwards_bounded_target():
    response = client.post("/api/reviews/collect", json={"max_reviews_per_product": 100})
    assert response.status_code == 200
    assert service.received == 100
    assert response.json()["requested_reviews"] == 400

@pytest.mark.parametrize("value", [0, 301])
def test_collect_endpoint_rejects_unsafe_target(value):
    assert client.post("/api/reviews/collect", json={"max_reviews_per_product": value}).status_code == 422
```

增加无 body 默认 100、最新运行为空时返回真实配置状态、服务异常转换为安全响应且不泄漏 Token 的测试。

- [ ] **Step 2: 运行测试确认 RED**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_review_api.py -v --basetemp backend/.pytest-tmp/api-red -p no:cacheprovider`

Expected: FAIL with 404 for `/api/reviews/collect`。

- [ ] **Step 3: 实现依赖与两个 Endpoint**

新增 `get_review_collection_service()` 依赖并可在测试中覆盖。`POST` 同步调用有界采集；BrightDataAPIError 映射为统一摘要而不是泄漏请求头。`GET latest` 只读 SQLite 与当前配置，不触发外部 API。

- [ ] **Step 4: 运行定向测试确认 GREEN**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_review_api.py backend/tests/test_api.py -v --basetemp backend/.pytest-tmp/api-green -p no:cacheprovider`

Expected: PASS。

### Task 5: 让 REAL VOC 合并真实来源并追溯双 URL

**Files:**
- Modify: `backend/app/schemas/models.py`
- Modify: `backend/app/data_providers/review_csv_provider.py`
- Modify: `backend/app/skills/voc_analysis.py`
- Modify: `backend/app/skills/report_generation.py`
- Modify: `backend/tests/test_voc_real_mode.py`
- Modify: `backend/tests/test_review_workflow.py`

**Interfaces:**
- Consumes: `REAL_REVIEW_SOURCE_TYPES`
- Produces: `Evidence.review_url: str | None`
- Produces: `Evidence.product_url: str | None`
- Preserves: `_real_voc(...)` 的 DeepSeek/Pydantic/Python 聚合流程

- [ ] **Step 1: 写 REAL/SAMPLE 隔离与 Evidence URL 失败测试**

```python
def test_real_workflow_uses_brightdata_and_imported_rows_only(tmp_path):
    store = seeded_store_with_brightdata_and_csv(tmp_path)
    real = run_real_workflow(store)
    assert real.voc["review_count"] == 2
    assert {e.source_type for e in real.evidence if e.id.startswith("ev-review-")} == {"IMPORTED_REAL", "BRIGHTDATA_REAL"}
    assert not any(e.data_nature == "SAMPLE" for e in real.evidence)

def test_brightdata_evidence_does_not_use_product_page_as_review_url():
    evidence = evidence_for_brightdata_row(review_url=None, product_url=PRODUCT_URL)
    assert evidence.review_url is None
    assert evidence.source_url is None
    assert evidence.product_url == PRODUCT_URL
```

同时断言无真实评论仍 `NEED_DATA`，DeepSeek 不可用仍 `NEED_LLM`，现有结构化聚合结果不变。

- [ ] **Step 2: 运行测试确认 RED**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_voc_real_mode.py backend/tests/test_review_workflow.py -v --basetemp backend/.pytest-tmp/voc-red -p no:cacheprovider`

Expected: FAIL，当前 REAL source guard 只接受 `IMPORTED_REAL`，Evidence 尚无双 URL。

- [ ] **Step 3: 最小修改现有 VOC**

ProviderResult 汇总来源改为 `REAL_REVIEW`；`run_voc_analysis()` 接受该汇总类型，逐行保留 `source_type` 和来源名称。Evidence：

```python
Evidence(
    source_url=row.get("review_url"),
    review_url=row.get("review_url"),
    product_url=row.get("product_url"),
    source_type=row["source_type"],
    ...,
)
```

不要修改批量大小 25、DeepSeek 调用、Pydantic 模型或 Python 聚合算法。报告把笼统“真实导入评论”改为“真实评论”，并分别列出 CSV 与 Bright Data 数量。

- [ ] **Step 4: 运行定向测试确认 GREEN**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_voc_real_mode.py backend/tests/test_review_workflow.py backend/tests/test_real_skill_calls.py -v --basetemp backend/.pytest-tmp/voc-green -p no:cacheprovider`

Expected: PASS。

### Task 6: 增加前端采集控制与中文统计

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/RealReviewData.tsx`
- Modify: `frontend/src/components/EvidencePanel.tsx`
- Modify: `frontend/src/display.ts`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Produces: `getLatestReviewCollection(): Promise<ReviewCollectionSummary>`
- Produces: `collectBrightDataReviews(maxReviewsPerProduct?: number): Promise<ReviewCollectionSummary>`
- Produces: `ReviewCollectionSummary` 和 `ReviewCollectionProductSummary` TypeScript types

- [ ] **Step 1: 先扩展 TypeScript 契约并运行构建确认 RED**

在 `types.ts` 定义后，先在 `RealReviewData.tsx` 引用尚不存在的 API 函数：

```ts
export type ReviewCollectionProductSummary = {
  brand: string; model: string; asin?: string; status: string
  requested_reviews: number; collected_reviews: number; valid_reviews: number
  duplicate_reviews: number; invalid_reviews: number
}
export type ReviewCollectionSummary = {
  status: string; credential_configured: boolean; target_products: number
  requested_reviews: number; collected_reviews: number; valid_reviews: number
  duplicate_reviews: number; invalid_reviews: number; products: ReviewCollectionProductSummary[]
  finished_at?: string | null
}
```

Run: `npm --prefix frontend run build`

Expected: FAIL，原因是 `getLatestReviewCollection` / `collectBrightDataReviews` 尚未导出。

- [ ] **Step 2: 实现 API 调用和 RealReviewData 状态**

页面加载时并行读取累计 stats 和 latest collection。点击“获取真实 Amazon 评论”后先设置本地 `COLLECTING`，请求返回后用真实摘要覆盖并刷新 stats。请求期间禁用 CSV 导入、真实分析和重复采集。

界面展示：Bright Data API 状态、目标评论、实际获取、有效、重复、无效、四款商品的 `实际 / 请求` 与有效数。`NOT_CONFIGURED`、`PRODUCT_URL_REQUIRED`、`SCHEMA_CONFIRMATION_REQUIRED`、`PARTIAL`、`FAILED` 都显示中文说明，数字永远来自接口。

- [ ] **Step 3: 更新 EvidencePanel 双 URL**

具体评论链接存在时显示“查看原始评论”；商品链接存在时单独显示“查看商品页面”。不得把商品链接放在评论链接标签下。链接使用 `target="_blank" rel="noreferrer"`。

- [ ] **Step 4: 运行构建确认 GREEN**

Run: `npm --prefix frontend run build`

Expected: PASS；无 TypeScript 错误，Vite 产物生成成功。

### Task 7: 文档、完整验证与受控真实 Smoke

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Verify: entire repository

**Interfaces:**
- Documents: `Bright Data → Normalize → ReviewStore → DeepSeek VOC`
- Documents: Mock → `1×5` → Schema confirmation → `4×100`

- [ ] **Step 1: 更新 README 与配置说明**

README 明确 SAMPLE 仅供 DEMO，`IMPORTED_REAL` 与 `BRIGHTDATA_REAL` 均为真实评论来源，采集不访问 Amazon HTML，实际数量不保证等于目标。写明五条 Probe 的位置、隐私白名单、`BRIGHTDATA_SCHEMA_CONFIRMED` 门禁，以及 `review_url`/`product_url` 的差异。不得写入 Token 示例值。

- [ ] **Step 2: 执行安全检查**

Run:

```powershell
git check-ignore .env data/reviews_real/reviews.sqlite3
git diff --check
git diff -- . ':!.env' | Select-String -Pattern 'BRIGHTDATA_API_TOKEN=.+' -CaseSensitive
git status --short
```

Expected: `.env` 和 SQLite 被忽略；无真实 Token 匹配；用户原有未跟踪文档保持未暂存。

- [ ] **Step 3: 运行完整后端测试**

Run: `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests -v --basetemp backend/.pytest-tmp/final -p no:cacheprovider`

Expected: 全部 PASS；若有既有弃用警告，逐条如实报告。

- [ ] **Step 4: 运行前端构建**

Run: `npm --prefix frontend run build`

Expected: PASS。若构建改写已跟踪缓存文件，仅恢复该生成文件，不覆盖用户修改。

- [ ] **Step 5: 运行离线 Smoke**

使用临时 SQLite、Fake Bright Data Client 和 DEMO runner，顺序执行而不共享 pytest 临时目录：

```powershell
C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_review_collection.py -v --basetemp backend/.pytest-tmp/collection-smoke -p no:cacheprovider
C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests/test_workflow.py -v --basetemp backend/.pytest-tmp/demo-smoke -p no:cacheprovider
```

Expected: API→Normalize→SQLite 合成链路通过；DEMO 仍使用 12 条 SAMPLE。

- [ ] **Step 6: 只读检查真实 Smoke 前置条件**

不得打印值，只输出布尔状态：Token 是否非空、四款 `amazon_url` 是否齐全、`BRIGHTDATA_SCHEMA_CONFIRMED` 是否为 true。

- [ ] **Step 7: 条件满足时执行一款五条真实 Smoke**

仅当 Token 与至少一个人工确认 URL 存在且 schema 尚未确认时调用一款×五条。检查 Schema Probe 字段名、类型、白名单预览、SQLite 有效/重复/无效数量以及 URL 语义。不要在同一轮自动把确认标志改为 true；报告 Probe 路径并等待人工确认。

- [ ] **Step 8: 仅在人工确认 Schema 后执行四款各一百条**

只有四个 URL 齐全且 `.env` 中确认标志已经由人工设为 true 才执行。统计 Requested、Collected、Valid、Duplicate、Invalid 及每款数量。任一条件缺失则不调用 API，并报告 `WAITING_FOR_CREDENTIALS`、`PRODUCT_URL_REQUIRED` 或 `SCHEMA_CONFIRMATION_REQUIRED`。

- [ ] **Step 9: 最终单次提交并推送**

再次确认分支为 `feature/pen-x1-agent`，精确暂存本轮文件，排除用户原有未跟踪文档、`.env`、SQLite、Probe 和构建产物：

```powershell
git branch --show-current
git status --short
git diff --cached --check
git commit -m "feat: collect real Amazon reviews via API"
git push origin feature/pen-x1-agent
```

Expected: 本地 HEAD 与 `refs/remotes/origin/feature/pen-x1-agent` 相同；没有 merge 或 force push。
