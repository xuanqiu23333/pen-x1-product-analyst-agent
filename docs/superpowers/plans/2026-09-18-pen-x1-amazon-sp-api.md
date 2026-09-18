# Amazon SP-API Manual Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add traceable manual Amazon Catalog, Pricing and Customer Feedback sync into PEN-X1's existing Fact/Evidence workflow.

**Architecture:** Keep Fixture/CSV providers. A cached LWA auth service supplies a bounded SP-API client; a provider normalizes official responses; a sync service writes sanitized snapshots; REAL analysis consumes latest production snapshot.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, httpx, React/TypeScript, existing Conda `pen-x1-agent`.

**Spec:** `docs/superpowers/specs/2026-09-18-pen-x1-amazon-sp-api-design.md`

## Global Constraints

- Work only in `D:\Projects\pen-x1-product-analyst-agent` on `feature/pen-x1-agent`.
- No Docker, venv, Redis, PostgreSQL, Kafka, Celery, Kubernetes, scheduler, scraper or credential logging.
- Do focused red/green tests during development; run full verification once after the main implementation.

---

### Task 1: LWA authentication and SP-API client

**Files:** `.env.example`, `backend/app/services/amazon_auth.py`, `backend/app/services/amazon_sp_api_client.py`, `backend/tests/test_amazon_client.py`.

**Interfaces:** `AmazonAuth.get_access_token() -> str`; `AmazonSPAPIClient.get(path, operation, params) -> dict`; `AmazonSPAPIClient.post(path, operation, payload) -> dict`; metrics on client.

- [x] Test token reuse, refresh margin, header contract, bounded 429 retry and sanitized 401 error with injected httpx transport. Confirm focused test fails due missing module.
- [x] Implement configuration loading, token cache and bounded client with only `x-amz-access-token`, `x-amz-date`, `user-agent` authentication headers.
- [x] Run focused tests green.

### Task 2: Provider normalization

**Files:** `backend/app/data_providers/amazon_sp_api_provider.py`, `backend/app/schemas/amazon.py`, `backend/tests/test_amazon_provider.py`.

**Interfaces:** `get_catalog_item`, `get_pricing`, `get_customer_feedback`, `get_customer_feedback_trends`, `sync_product`. Missing fields stay null. Feedback topics and trends are separate.

- [x] Test Catalog summary/rank, item offer pricing, positive/negative topic metrics, trend parsing and missing fields; confirm focused red.
- [x] Implement the four official read operations and Pydantic records.
- [x] Run focused tests green.

### Task 3: Manual sync, snapshots and API

**Files:** `backend/app/services/amazon_sync.py`, `backend/app/api/routes.py`, `data/config/amazon_competitors.json`, `.gitignore`, `backend/tests/test_amazon_sync.py`.

**Interfaces:** `sync_all_competitors() -> AmazonSyncSummary`; read-only snapshot getters; five `/api/amazon` endpoints.

- [x] Test no-credential/no-ASIN safety, partial failure counts, sanitized snapshot persistence and API outcomes; confirm focused red.
- [x] Implement sync summary, Fact/Evidence normalization, dated history and latest snapshot, route wiring.
- [x] Run focused tests green.

### Task 4: Existing workflow and small UI integration

**Files:** `backend/app/workflow/runner.py`, selected existing skills, `frontend/src/api.ts`, `frontend/src/App.tsx`, new sync panel, `frontend/src/display.ts`, `frontend/src/styles.css`, `README.md`, focused workflow test.

- [x] Test production snapshot consumed in REAL and ignored in DEMO, feedback/CSV counts remain separate, report source label; confirm focused red.
- [x] Wire normalized snapshot into competitor/VOC/opportunity/decision/report, preserving existing fallback.
- [x] Add manual sync panel and Chinese labels; run focused tests.

### Task 5: FINAL VERIFICATION and feature branch delivery

- [x] Run complete `pytest` (27 passed), frontend production build and no-credential DEMO/API smoke. Hosted sandbox and production smoke require credentials and verified ASIN; none are currently configured.
- [ ] Review `git status`, `git diff`, secret/ignored paths, commit and push only `feature/pen-x1-agent`.
