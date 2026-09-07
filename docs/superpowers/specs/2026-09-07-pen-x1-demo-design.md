# PEN-X1 Product Analyst Agent Demo Design

## Goal

Build a Windows-local interview demo that guides the PEN-X1 pen flashlight through a traceable ten-skill product-analysis workflow and produces a validated Markdown launch-feasibility report for Amazon US.

## Scope and constraints

- The root directory is `D:\Projects\pen-x1-product-analyst-agent`; all application files live below it.
- Use React, TypeScript, Vite, Tailwind CSS, npm, Python 3.11, FastAPI, Pydantic v2, Pandas, JSON/CSV, and optional SQLite only.
- Use the dedicated Conda environment `pen-x1-agent`; do not create a venv or use Docker.
- Use DeepSeek only through a backend LLM provider configured by `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL`.
- `DEMO_MODE=true` must run the full workflow without network access or an API key.
- Do not implement live Amazon scraping, paid market-tool integrations, WebSockets, infrastructure services, or SaaS features.

## Architecture

The backend owns a typed `AnalysisState` with project facts, outputs from ten skills, evidence, report data, validation data, and per-skill run status. A straightforward sequential workflow invokes one isolated skill per stage; the workflow boundary is deliberately narrow so a future LangGraph adapter can call the same skill interfaces.

Each skill is deterministic where possible. Fixture providers load market and competitor information; Pandas normalizes sample CSV reviews; Python calculates counts, risk scores, and profitability. The provider receives only bounded semantic-generation tasks, validates structured output, and falls back to deterministic mock output in demo mode. The independent report validator runs after report generation and can change the report status to `REVIEW_REQUIRED`.

## Backend components

- `app/schemas/`: Pydantic types for facts, evidence, reviews, risks, opportunities, profit scenarios, gates, decisions, state, API responses, and reports.
- `app/skills/`: `material_check`, `market_research`, `competitor_analysis`, `voc_analysis`, `opportunity_analysis`, `technical_risk`, `lifecycle_risk`, `profit_analysis`, `swot_decision`, and `report_generation`.
- `app/services/`: deterministic profit calculator and data-loading helpers.
- `app/llm/`: provider interface, DeepSeek implementation, mock implementation, and provider factory. Skills do not import SDKs directly.
- `app/workflow/`: ordered executor that records state transitions and handles an individual skill failure without crashing the API.
- `app/validators/`: report validator for facts, unsupported claims, status language, evidence coverage, conflicts, and calculated numeric claims.
- `app/api/`: analysis-run, run-status, skill-result, evidence, and report endpoints.

## Data contract

Facts include a source, source level, status, confidence, and data nature. The supplied PEN-X1 product details are `FACT`. Competitor/market fixture entries are `PUBLIC_FIXTURE`. Review CSV entries are clearly `SAMPLE`. Price and return-rate sensitivity inputs are `SCENARIO`. Any absent parameter is `UNKNOWN` or `NEED_VERIFY`; no skill invents a specification.

Risks include their lifecycle stage, module, cause, trigger, impact, evidence, validation method, mitigation, and status. Severity, probability, and detectability are only scored when supported; a missing probability remains null. Opportunities require user-problem evidence, competitor-gap evidence, and a PEN-X1 capability before they can be more than `NEED_VERIFY`.

## Frontend

The React single-page dashboard has a concise header with product context and mode, a left-side ten-skill pipeline, a central result workspace, and a right-side evidence inspector. The completed dashboard prioritizes top user pain points, risk cards, product gates, a profit sensitivity matrix, and the decision. Polling is used only while a run is active. Fixture and sample labels remain visible throughout.

## APIs

- `POST /api/analysis-runs`: starts a DEMO or REAL run.
- `GET /api/analysis-runs/{run_id}`: returns current workflow status and skill statuses.
- `GET /api/analysis-runs/{run_id}/skills/{skill_id}`: returns a structured skill result.
- `GET /api/analysis-runs/{run_id}/evidence/{evidence_id}`: returns inspectable source evidence.
- `GET /api/analysis-runs/{run_id}/report`: returns report metadata and Markdown.

## Failure handling

Invalid model output is retried a small bounded number of times in REAL_MODE and marks only the affected skill as failed if recovery is not possible. DEMO_MODE never contacts external systems. A failed skill preserves the remaining state, makes missing downstream conclusions pending, and shows a clear warning in the UI.

## Verification

Tests cover known facts remaining unfilled, deterministic profit calculation, opportunity evidence requirements, risk-score behavior with unknown probabilities, validator claim/status rules, and an end-to-end demo workflow. Final verification runs the backend test suite, Vite production build, backend and frontend startup, a full DEMO_MODE run, and a lightweight REAL_MODE provider smoke test only when valid credentials are present.
