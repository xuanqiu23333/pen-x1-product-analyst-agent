# PEN-X1 第二轮 Agent 升级设计

## 目标

在保留既有十个 Skill、离线 DEMO_MODE 和界面的前提下，将固定演示数据升级为可追踪的 Provider 数据流、可注入的 DeepSeek 结构化分析、证据链、声明校验与规则驱动决策。

## 约束

仅在 `feature/pen-x1-agent` 修改；仅操作本项目目录；继续使用 Conda `pen-x1-agent` / Python 3.11、现有 Node/npm；不使用 Docker、代理、验证码规避、Amazon 评论爬虫或生产级基础设施。网络 Provider 只发起普通 HTTP 请求，最长 15 秒、最多两次尝试，失败后记录原因并降级。

## 数据与 Provider

新增 `data_providers`：按最小职责拆分为市场/竞品数据读取、官网数据、Amazon 商品摘要和评论 CSV。FixtureProvider 保持 DEMO_MODE 的确定性。OfficialWebsiteProvider 对四个指定品牌执行普通网页请求、HTML 字段提取与标准化；无可用页面或字段时返回 `UNAVAILABLE`。AmazonProductProvider 仅采集公开商品摘要，始终是尽力而为能力，不能采集评论或规避访问限制。

所有 Provider 返回 `ProviderResult`：记录 `status`、`source_type`、`source_url`、`retrieved_at`、`fallback_reason` 和标准化数据。Runner 将真实结果与 Fixture 合并，不静默覆盖冲突；字段差异形成 `CONFLICT` 记录。

## LLM 与 Skill

Runner 只创建一次 LLM Provider，并显式注入 VOC、机会、技术风险、生命周期风险、SWOT/决策与报告 Skill。REAL_MODE 调用 DeepSeek 取得 JSON，再用 Pydantic 模型校验；无效、超时或 API 错误会产生 Skill Warning 并使用规则/Fixture 结果。DEMO_MODE 只用 MockLLMProvider 和 FixtureProvider。

VOC 的 REAL_MODE 由 LLM 分类评论的情感和 Aspect，Python 负责去重、频次、比例、排序与产品分布。所有 Pain Point 保存 `ev-review-*` 证据 ID。Opportunity 由 VOC、竞品、市场、内部产品 Fact 四类引用生成；任一缺失则为 `NEED_VERIFY`。

## 校验与决策

引入 `Claim`，由报告结构化声明生成器提取关键声明。Validator 检查声明绑定的 Fact/Evidence、状态语言、来源冲突和数字来源；保留少量危险参数保护规则但不再以词表为主。DecisionEngine 根据计算出的五个 Gate 生成 GO、CONDITIONAL_GO 或 NO_GO；只有 SAMPLE/Fixture 市场数据时 Market Gate 最多为 PARTIAL。

## 界面

保留三栏布局，新增数据源状态卡片，Evidence 元数据，Provider 降级原因和 Skill 的输入/数据源/动作/输出/证据/警告摘要。界面以中文显示，来源真实性通过“实时 / Fixture / 示例 / 降级 / 未知”明确区分。

## 验证

测试 Provider 正常与降级、VOC 模型校验和 Python 聚合、Opportunity 证据完整性、冲突、Claim 校验、Gate/Decision、完整 DEMO_MODE 工作流。最终执行 pytest、npm build、DEMO_MODE 完整运行；仅在环境存在有效 DeepSeek 密钥时执行 REAL_MODE 冒烟。官网 Provider 至少尝试一个公开页面，失败也必须验证降级。
