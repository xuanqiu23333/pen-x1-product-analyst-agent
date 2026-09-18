# PEN-X1 Real Review Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立真实 CSV 评论的 SQLite 导入、隔离 VOC、可追溯 Evidence 与前端覆盖统计。

**Architecture:** 原样例 CSV Provider 保留给 DEMO；真实导入服务独立存 SQLite，REAL Runner 只从真实 Provider 取有效评论。结构化模型负责语义校验，Python 负责计数和均值。

**Tech Stack:** Python 3.11、stdlib sqlite3/csv、FastAPI、Pydantic 2、React/TypeScript。

**Spec:** `docs/superpowers/specs/2026-09-18-real-review-pipeline-design.md`

## Global Constraints

- 只在 `D:\Projects\pen-x1-product-analyst-agent`、`feature/pen-x1-agent` 改动；不合并 main/dev。
- Conda `pen-x1-agent` + Python 3.11；沿用现有 Node/npm；不创建 venv、不装 Docker/Redis 等。
- 不抓取 Amazon 评论页，不使用代理池、验证码绕过、Selenium/Playwright。
- 真实 CSV 和 SQLite 不提交；既有未跟踪任务文档不暂存。
- 主体完成后统一全量 pytest/build；开发中只跑相关小测试。

---

### Task 1: 清洗、SQLite 与 Provider

**Files:** `backend/app/services/review_cleaning.py`, `backend/app/services/review_store.py`, `backend/app/data_providers/review_csv_provider.py`, `backend/tests/test_review_import.py`, `.gitignore`。

**Interfaces:** `ReviewStore(db_path).import_csv(csv_text) -> dict`；`stats() -> dict`；`valid_reviews() -> list[dict]`；`ReviewCsvProvider(data_root, mode='DEMO', db_path=None).get_reviews()`。

- [x] 写真实 CSV 导入、invalid、重复 ID、无 ID hash、重复批次和字段白名单测试。
- [x] 跑 `python -m pytest backend/tests/test_review_import.py -q`，确认新能力导致预期失败。
- [x] 用 `apply_patch` 实现清洗与两表事务存储，按真实/样例模式分源。
- [x] 定向测试变绿，并检查 SQLite 只保存白名单字段。

### Task 2: API 与统计

**Files:** `backend/app/api/routes.py`, `backend/tests/test_review_api.py`。

**Interfaces:** `POST /api/reviews/import`（UTF-8 CSV 原始请求体）；`GET /api/reviews/stats`（累计数量、占比、覆盖等级、每竞品数量）。

- [x] 写 API 成功/错误大小与统计测试，确认红灯。
- [x] 实现受限 CSV 导入和只读统计路由，测试变绿。

### Task 3: REAL VOC 与 Evidence

**Files:** `backend/app/skills/voc_analysis.py`, `backend/app/prompts/voc.py`, `backend/app/schemas/models.py`, `backend/app/workflow/runner.py`, `backend/app/llm/factory.py`, `backend/app/skills/report_generation.py`, `backend/tests/test_voc_real_mode.py`, `backend/tests/test_amazon_workflow.py`, `backend/tests/test_review_workflow.py`。

**Interfaces:** REAL 的 `run_voc_analysis` 只接收 `IMPORTED_REAL`；输出 `status`、`review_count`、Pain Points 和来源；`ev-review-*` 对应入库行。

- [x] 写无真实数据 NEED_DATA、真实评论结构化聚合、无 LLM NEED_LLM、Evidence 详情、Demo 隔离测试并确认红灯。
- [x] 实现 Pydantic 校验、Python 聚合、Runner 模式选择和报告来源文案；定向测试变绿。

### Task 4: 前端与文档

**Files:** `frontend/src/components/RealReviewData.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/display.ts`, `frontend/src/components/ResultPanel.tsx`, `frontend/src/components/EvidencePanel.tsx`, `frontend/src/styles.css`, `README.md`。

- [x] 在现有页面加中文 CSV 导入、统计与四竞品分布，区分 REAL/DEMO VOC 和证据明细。
- [x] 文档写明 CSV 模板、导入方法、覆盖等级为内部定义、用户需确保来源授权。

### Task 5: Final Verification 与交付

- [x] 运行 `C:\Users\86166\anaconda3\envs\pen-x1-agent\python.exe -m pytest backend/tests -v --basetemp backend/.pytest-tmp`。
- [x] 运行 `npm --prefix frontend run build`，排除构建缓存变更。
- [x] 运行合成 CSV 导入 smoke 与 DEMO workflow smoke；不得称合成数据为真实 Amazon 抓取。
- [x] 检查 git diff、密钥/SQLite 忽略和固定分支，仅暂存本轮文件。
- [ ] 提交 `feat: add real review ingestion pipeline` 并推送 `origin/feature/pen-x1-agent`。
