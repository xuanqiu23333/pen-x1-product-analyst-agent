# PEN-X1 Real Review Pipeline 设计

## 边界

仅导入用户有权使用的 CSV；不访问 Amazon 评论页面，不使用爬虫或浏览器自动化。`IMPORTED_REAL` 表示用户提供的非样例评论，系统不独立核验 Amazon 来源。原有四个演示 CSV 只供 DEMO 模式使用，不迁移为真实数据。真实 SQLite 文件位于 `data/reviews_real/reviews.sqlite3`，不纳入 Git。

## 数据流

`text/csv` 导入 → 白名单字段映射 → Unicode/HTML/空白清洗 → 校验 → SQLite `review_raw`（VALID/DUPLICATE/INVALID）及 `review_collection_run` → 仅 VALID 的真实评论 Provider → DeepSeek JSON → Pydantic 校验 → Python 去重聚合 → VOC/Evidence → Agent 下游技能与报告。

`review_raw` 只存指定评论字段，不存 reviewer 姓名、电邮或 CSV 未声明列。有效评论按稳定 `external_review_id` 优先去重；缺 ID 时按 `asin + normalized_review_text + rating + review_date` 的 SHA-256 去重。事务内判重，重复行保留审计状态但不参与 VOC。无效行只记录安全白名单字段和状态；缺失值可为空。

## 模式隔离与失败状态

DEMO 继续使用原样例 Provider 和离线规则分析。REAL 只读 SQLite 中 `IMPORTED_REAL` 且 `VALID` 的评论。真实有效评论为零时 VOC=`NEED_DATA`，评论数 0，不读取样例。存在真实评论但 DeepSeek 未配置、失败或结构错误时 VOC=`NEED_LLM`，不启用样例或规则替代分类；已导入评论及其来源证据仍可追溯。Amazon 官方聚合 Feedback 与原始评论仍分开计数。

## 统计与追溯

统计累计 raw/valid/duplicate/invalid、真实与样例占比、最近采集时间、按四款竞品的有效评论数。覆盖等级仅为本项目 Demo 内部：0=NEED_DATA，1–49=LOW_COVERAGE，50–199=PARTIAL，200+=SUFFICIENT_FOR_DEMO。每个 Pain Point 的 `evidence_review_ids` 仅引用实际参与聚合的 `ev-review-*`；Evidence 记录商品、ASIN、评分、日期、正文、helpful、链接、采集时间和导入来源。均值、提及次数、频率及商品分布由 Python 计算。

## 接口与界面

新增 `POST /api/reviews/import`，请求体为 UTF-8 CSV（`text/csv`），字段固定为 `review_id,asin,product,rating,title,review_text,date,verified,helpful,source_url`；限定大小并返回该次导入摘要。新增 `GET /api/reviews/stats` 返回累计统计与四竞品计数。前端保留原主布局，增加中文“真实评论数据”区、CSV 选择/导入、数量/占比/覆盖等级/最近采集及竞品分布。REAL VOC 标签和报告明确标注导入数据及非平台核验；DEMO 标签保持样例身份。

## 验证

定向测试覆盖清洗、无效数据、ID/hash 去重、重复导入、来源隔离、VOC 结构化校验与 Python 聚合、Evidence 追溯、统计和 API。主体完成后统一运行后端 pytest、前端 build、合成真实 CSV 导入 smoke 与离线 DEMO workflow smoke。合成 smoke 不宣称取得真实 Amazon 评论。
