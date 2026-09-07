你现在是该项目的主开发工程师，请直接在当前项目目录中完成一个可运行、可现场演示的【PEN-X1 手电筒产品分析师 AI Agent Demo】。

# 一、项目背景

这是一个求职面试作业 Demo。

业务要求是基于海外大模型搭建一个：

【手电筒产品分析师 AI Agent】

新品信息：

- 产品：PEN-X1 笔式手电
- 销售渠道：Amazon US / 北美亚马逊
- 目标售价：34.95 美元
- 目标人群：
  - EDC 爱好者
  - 家用应急用户
  - 轻度户外用户

核心产品特性：

支持 5 种电池供电：

1. 1×14500
2. 1×AA
3. 1×AAA
4. 2×AA
5. 2×AAA

现有技术方案：

- BOOST 驱动
- 电池识别
- 机械补偿方案

已知 BOM：

- 不含电池：48.6 元人民币
- 含电池：57.6 元人民币

指定竞品：

1. ThruNite Archer 2A C
2. Streamlight MicroStream
3. Nitecore MT2A Pro
4. Weltool T1 Pro

------

# 二、Demo 最终目标

不要把它做成普通的“聊天机器人”。

我要展示的是一个：

“有明确业务流程、有 Skill 边界、有结构化数据流、有数据来源、有证据链、有风险判断能力的产品分析 Agent”。

现场点击：

【开始分析 PEN-X1】

之后能够看到：

资料检查
↓
市场调研
↓
竞品分析
↓
Amazon VOC 评论分析
↓
市场机会挖掘
↓
产品技术风险分析
↓
研发 / 量产 / 北美上市风险分析
↓
价格利润分析
↓
SWOT 与产品决策
↓
最终报告生成
↓
独立结果校验

最终生成：

《PEN-X1 北美市场产品调研与上市可行性分析报告》

------

# 三、开发原则

## 1. 这是面试 Demo，不是商业正式系统

优先级：

1. 流程完整
2. Skill 边界清晰
3. 数据来源清楚
4. 结果可追溯
5. 防幻觉机制明显
6. 风险分析专业
7. 页面适合投屏演示
8. 运行稳定

不优先：

- 复杂账号系统
- 权限管理
- 多租户
- Kubernetes
- 微服务
- 消息队列
- 商业支付
- 大规模爬虫
- 复杂数据中台

坚持 YAGNI。

------

# 四、推荐技术栈

优先采用：

## 前端

- React
- TypeScript
- Vite
- Tailwind CSS
- 可使用成熟 UI 组件库，但不要为了 UI 引入过度复杂依赖

## 后端

- Python 3.11+
- FastAPI
- Pydantic v2

## Agent

优先：

- LangGraph

如果 LangGraph 对当前 Demo 带来明显额外复杂度，可以使用：

- 显式 Python Workflow / State Machine

但整个结构必须保留未来迁移 LangGraph 的能力。

## 大模型

默认使用：

OpenAI API

通过环境变量配置：

OPENAI_API_KEY
OPENAI_MODEL

不要将 API Key 写入代码。

模型调用必须封装 Provider 层，避免业务代码直接到处调用 OpenAI SDK。

目录示例：

backend/app/llm/provider.py

未来理论上可以切换 Claude / Gemini，但第一版不需要真正实现多个模型。

------

# 五、必须支持两种运行模式

这是 Demo 稳定性的关键。

## MODE 1：REAL_MODE

如果存在：

OPENAI_API_KEY

允许调用真实海外大模型完成：

- 评论分类
- 机会分析
- 风险分析
- SWOT
- 报告生成

## MODE 2：DEMO_MODE

如果没有 OPENAI_API_KEY：

系统仍然必须可以完整运行。

使用：

fixtures / demo data / mock provider

返回预先设计好的结构化结果。

也就是说：

现场即使网络或 API 出问题，也不能导致 Demo 无法演示。

环境变量：

DEMO_MODE=true

------

# 六、项目整体架构

建议：

frontend/
backend/
data/
docs/

Backend 内部：

app/
├── api/
├── core/
├── models/
├── schemas/
├── skills/
├── workflow/
├── llm/
├── services/
├── validators/
├── repositories/
└── main.py

data/

├── internal/
├── competitors/
├── reviews/
├── fixtures/
└── outputs/

------

# 七、核心数据模型：AnalysisState

所有 Skill 不要通过长文本互相传输。

建立统一的：

AnalysisState

至少包含：

project
facts
market
competitors
voc
opportunities
technical_risks
lifecycle_risks
profit_analysis
swot
decision
report
validation
skill_runs

每个 Skill：

只读取需要的字段；
输出结构化数据；
写回 AnalysisState。

------

# 八、统一 Fact 数据模型

所有关键事实必须能够追踪来源。

设计类似：

Fact {
id
category
name
value
unit
source_type
source_name
source_url
source_date
status
confidence
}

status 只允许：

CONFIRMED
INFERRED
UNKNOWN
NEED_VERIFY
CONFLICT

含义：

CONFIRMED：
来源明确的事实

INFERRED：
根据已有证据推导出的判断

UNKNOWN：
当前没有资料

NEED_VERIFY：
需要实验或人工确认

CONFLICT：
多个来源之间存在冲突

------

# 九、数据来源等级

建立 SourceLevel：

L1_INTERNAL

企业内部：

- PEN-X1 产品资料
- 技术方案
- BOM
- 利润模型

L2_OFFICIAL

官方：

- 品牌官网
- Amazon 商品页
- Amazon 官方 API

L3_MARKET_TOOL

第三方市场数据：

- Helium 10
- Jungle Scout
- Keepa

当前 Demo 可以先使用导入结构，不要求真实调用付费 API。

L4_VOC

用户声音：

- Amazon Reviews
- Customer Review Insights
- 用户评论 CSV

L5_COMMUNITY

辅助：

- Google Trends
- 专业测评
- Reddit
- Forum

界面中需要明显显示：

Source
Status
Confidence

------

# 十、10 个 Skill

必须实现为独立模块。

不要写成一个巨型 prompt。

------

# Skill 01：资料完整性检查

文件建议：

skills/material_check.py

输入：

- PEN-X1 项目资料
- BOM
- 技术方案
- 目标售价
- 目标人群
- 竞品清单

执行：

检查已知与未知数据。

必须识别例如：

已知：

- 售价 34.95 USD
- BOM 48.6 / 57.6 RMB
- 五种电池
- BOOST
- 电池识别
- 机械补偿

未知：

- PEN-X1 最大流明
- 不同电池实际流明
- 续航
- 防水等级
- 重量
- 尺寸
- 温升
- 认证状态

这些未知参数绝对不能自动补全。

输出：

MaterialCheckResult

包含：

confirmed
unknown
need_verify
external_research_required

------

# Skill 02：市场调研

skills/market_research.py

第一版 Demo 不需要开发 Amazon 爬虫。

设计统一 MarketDataProvider。

支持：

FixtureMarketProvider

未来：

AmazonMarketProvider
Helium10Provider
JungleScoutProvider
GoogleTrendsProvider

Demo 数据允许来自：

data/fixtures/market.json

字段包括：

keyword
price_range
product_count_sample
rating
review_count
battery_type
main_features
source
status

必须在页面注明：

“演示数据 / 示例公开数据”

不要把 fixture 伪装成实时 Amazon 数据。

输出：

MarketResearchResult

包括：

price_segments
common_features
battery_patterns
customer_scenarios
market_observations
sources

------

# Skill 03：竞品分析

skills/competitor_analysis.py

针对：

- ThruNite Archer 2A C
- Streamlight MicroStream
- Nitecore MT2A Pro
- Weltool T1 Pro

统一 Competitor 数据模型：

brand
model
price
max_lumen
battery
runtime
weight
size
ip_rating
charging
modes
clip
selling_points
limitations
source
source_status

注意：

如果 Demo fixture 中没有某参数：

不要猜。

使用：

null
UNKNOWN

页面展示：

竞品矩阵。

必须支持：

参数对比
供电方式对比
价格对比
定位对比
主要优势
主要不足

------

# Skill 04：Amazon 评论 / VOC 痛点分析

skills/voc_analysis.py

这是核心展示模块之一。

不要开发 Amazon 全站爬虫。

第一版读取：

data/reviews/*.csv

提供至少四款竞品的 Demo 评论 CSV。

每条 Review：

review_id
product
asin
rating
title
review_text
date
verified
helpful
source

如果真实评论数据暂时没有：

使用明确标记为 SAMPLE / DEMO 的示例数据。

绝对不能声称：

“分析了真实 Amazon 5000 条评论”

除非真的有数据。

执行流程：

1. 数据清洗
2. 去重
3. 情感判断
4. Aspect 分类
5. Pain Point 提取
6. 高频统计
7. 严重程度判断
8. 保存 Evidence

Aspect 至少包括：

brightness
runtime
battery
charging
switch
modes
clip
size
weight
durability
waterproof
heat
beam
price

输出：

VOCResult

每个痛点：

pain_point
aspect
mentions
frequency
severity
products
evidence_review_ids
confidence

LLM 负责：

分类、语义归一化

Python 负责：

次数、比例等确定性统计。

页面必须支持点击某个痛点查看对应 Review Evidence。

------

# Skill 05：市场机会挖掘

skills/opportunity_analysis.py

禁止模型直接：

“给我想几个市场机会”。

机会必须满足：

# 用户需求证据 + 竞品缺口证据 + PEN-X1 产品能力

候选市场机会

Opportunity 数据模型：

id
title
user_problem
voc_evidence
competitor_gap
product_capability
market_evidence
confidence
status
validation_needed

例如：

供电自由度

产品事实：

PEN-X1 支持：

14500 / AA / AAA / 2AA / 2AAA

如果 VOC 和竞品数据也支持：

则可以生成 Candidate Opportunity。

如果证据不足：

status = NEED_VERIFY

不要写成“已经验证的市场机会”。

------

# Skill 06：产品技术风险分析

skills/technical_risk.py

这是整个项目的重点。

风险不能只是让 LLM：

“列举产品风险”。

采用二维风险扫描机制：

维度一：产品模块

- 电池系统
- BOOST 驱动
- 电池识别
- 机械补偿
- 光学 / LED
- 热管理
- 结构
- 防水
- 用户交互

维度二：生命周期

- 产品设计
- EVT
- DVT
- PVT
- 量产

重点识别：

## 五电池兼容测试复杂度

测试组合至少考虑：

Battery Configuration
×
Brand
×
SOC
×
Temperature
×
Operating Mode

不要直接生成巨量组合测试。

Agent 应给出：

Risk-Based Test Prioritization。

## BOOST 风险

关注：

- Vin
- Iin
- Vout
- Iout
- efficiency
- temperature
- output stability

## 电池识别风险

关注：

AA / AAA / 14500：

- 电压重叠
- SOC
- 品牌差异
- 温度变化
- 误识别

未知概率：

不要编数字。

status：

NEED_VERIFY

## 14500 热风险

只能描述：

Potential Risk

不能说：

“PEN-X1 存在严重过热”。

建议验证：

30 秒
1 分钟
3 分钟
5 分钟
10 分钟

但温度合格标准没有资料时：

标记：

PROJECT_THRESHOLD_REQUIRED

不要自己编造标准。

## 机械补偿

分析：

- 电池长度
- 电池直径
- 接触压力
- 弹簧压缩
- 松动
- 跌落瞬断
- 磨损
- 公差叠加

输出：

TechnicalRiskResult

------

# 十一、统一 Risk 数据模型

RiskCard：

risk_id
stage
module
risk
cause
trigger
impact
severity
probability
detectability
evidence
validation_method
mitigation
status

允许使用：

Severity：1-5
Probability：1-5
Detectability：1-5

Risk Score：

S × P × D

但是：

如果 Probability 没有数据：

不要让模型随便填。

允许：

probability = null

status = NEED_VERIFY

不要自行定义：

“超过 60 必须停产”

因为业务没有提供风险阈值。

------

# Skill 07：研发 / 量产 / 海外上市风险

skills/lifecycle_risk.py

与 Skill 06 区分：

Skill 06：

产品设计本身哪里可能出问题。

Skill 07：

这个产品从设计到 Amazon 消费者手里，哪里可能失败。

生命周期：

产品定义
↓
研发
↓
EVT
↓
DVT
↓
PVT
↓
量产
↓
运输
↓
仓储
↓
Amazon Listing
↓
消费者使用
↓
售后
↓
退货

分析至少包括：

产品定义：

- 五电池是否过度复杂
- 消费者是否理解价值

研发：

- 电气兼容
- 电池识别
- 温升
- 机械兼容

量产：

- 电池仓公差
- 弹簧一致性
- 接触阻抗
- 来料波动
- 装配错误
- 防水一致性

建议设计：

Five-Battery Compatibility EOL Test

但是不要要求每一台人工装五种消费电池。

可以提出：

标准化电池模拟治具 / 极限尺寸治具。

运输：

如果产品 SKU 包含 14500：

标记：

Lithium Shipping Risk

具体法规结论如果没有实时数据：

标记：

EXTERNAL_COMPLIANCE_VERIFY

不要自动声称已经满足。

Amazon：

- Listing 描述是否清楚
- 不同电池性能差异是否容易误解
- 消费者是否错误安装
- 性能宣传是否过度
- 差评与退货风险

形成完整：

Risk → Cause → Validation → Mitigation

输出：

LifecycleRiskResult

------

# Skill 08：价格与利润分析

skills/profit_analysis.py

绝对禁止让 LLM 做利润心算。

单独写：

services/profit_calculator.py

所有计算使用 Python。

输入：

售价场景：

29.95
32.95
34.95
36.95
39.95

注意：

这些是 Scenario，不是市场事实。

退货率场景：

3%
5%
8%
10%
15%

同样标记：

Scenario

SKU：

A：不含电池

B：含电池

已知：

BOM A：

48.6 RMB

BOM B：

57.6 RMB

其他成本如果没有真实输入：

例如：

- FBA
- Commission
- Ads
- Freight
- Tariff

允许用户在页面填写。

默认：

UNKNOWN

不要自己编造。

计算：

Revenue

- BOM
- Amazon Fee
- FBA
- Freight
- Advertising
- Return Cost
  =
  Contribution Margin

前端展示：

价格 × 退货率敏感性矩阵。

------

# Skill 09：SWOT 与产品决策

skills/swot_decision.py

禁止产生没有上游证据的新事实。

S：

Internal Positive

W：

Internal Negative

O：

External Positive

T：

External Negative

每条 SWOT 必须绑定：

evidence_ids

最终决策：

GO
CONDITIONAL_GO
NO_GO

当前 Demo 在缺少：

- PEN-X1 实测性能
- 全量 VOC
- 五电池可靠性测试
- 温升
- 量产数据
- 完整成本参数

情况下：

默认应该倾向：

CONDITIONAL_GO

但不要硬编码结论。

由规则 + 上游状态计算。

------

# 十二、五个 Product Gate

设计：

Market Gate

确认：

市场需求和用户痛点证据是否足够。

Product Gate

确认：

价值主张与用户需求是否匹配。

Technical Gate

确认：

五电池、识别、BOOST、温升、机械兼容是否验证。

Manufacturing / Launch Gate

确认：

量产一致性、EOL、运输和 Listing 风险。

Financial Gate

确认：

利润模型是否达到项目定义要求。

页面展示每个 Gate：

PASS
FAIL
PENDING

当前缺资料时：

PENDING

禁止为了让 Demo 看起来漂亮全部 PASS。

------

# Skill 10：最终报告生成

skills/report_generation.py

根据 AnalysisState 生成：

完整 Markdown 报告。

报告包括：

# PEN-X1 北美市场产品调研与上市可行性分析报告

## 1. 执行摘要

## 2. 项目背景

## 3. 数据来源与数据完整性

## 4. 北美市场调研

## 5. 四款竞品分析

## 6. 用户 VOC 与真实痛点

## 7. PEN-X1 市场机会

## 8. SWOT

## 9. 产品技术风险

## 10. 研发 / EVT / DVT / PVT 风险

## 11. 量产风险

## 12. 北美运输与 Amazon 上市风险

## 13. 价格利润敏感性分析

## 14. Product Gate

## 15. GO / CONDITIONAL GO / NO-GO

## 16. 后续验证计划

报告内：

CONFIRMED 与 INFERRED 必须区别表达。

UNKNOWN / NEED_VERIFY 不能被润色成确定事实。

------

# 十三、独立结果校验器

不要让“报告生成模型自己审自己”。

实现：

validators/report_validator.py

至少做：

## Fact Check

报告中的数字是否存在于 Fact Store。

## Unsupported Claim Check

报告是否包含：

Fact Store 中不存在的产品参数。

## Status Check

UNKNOWN 是否被写成确定性结论。

## Evidence Check

高重要度：

Opportunity
Risk
SWOT

是否绑定 Evidence。

## Conflict Check

多个数据源存在价格 / 参数版本冲突时：

报告是否正确说明。

## Numeric Check

利润等数字是否来源于计算模块。

输出：

ValidationResult

包括：

passed
warnings
errors

如果存在严重 error：

最终报告状态：

REVIEW_REQUIRED

页面必须明显显示。

------

# 十四、LLM Prompt 设计原则

每个 Skill 可以拥有自己的 Prompt Template。

但是：

不要把系统实现成 10 个纯 Prompt 文件。

真正逻辑应该包括：

Data Provider
↓
Preprocessing
↓
Schema
↓
LLM
↓
Pydantic Validation
↓
Business Rule
↓
Evidence Binding
↓
Output

LLM 只是其中一个组件。

------

# 十五、Structured Output

所有模型结果必须通过 Pydantic Schema 校验。

禁止直接：

response.text → 前端。

建议：

LLM
↓
JSON
↓
Pydantic
↓
Validation
↓
AnalysisState

模型返回格式错误时：

最多自动修复 / 重试合理次数。

仍失败：

Skill 标记 FAILED。

不能导致整个应用崩掉。

------

# 十六、前端页面设计

这是面试现场投屏。

不要做成复杂后台系统。

推荐一个页面：

顶部：

PEN-X1 产品分析师 AI Agent

显示：

Amazon US
Target Price $34.95
5 Battery Configurations

右上角：

REAL MODE / DEMO MODE

------

左侧：

Skill Pipeline

01 资料检查
02 市场调研
03 竞品分析
04 Amazon VOC
05 市场机会
06 技术风险
07 研发/量产/上市风险
08 利润分析
09 SWOT / Decision
10 最终报告

状态：

Pending
Running
Completed
Warning
Failed

点击 Skill：

可以查看结果。

------

中间：

当前 Skill 结果。

比如竞品矩阵、VOC、Risk Cards。

------

右侧：

Evidence / Source Panel

显示：

Evidence ID
Source
Status
Confidence

点击：

查看原始内容。

------

# 十七、Dashboard 必须重点展示

首页分析完成后显示：

## Key Findings

例如：

- 5 Battery Compatibility：核心产品能力
- Supply Flexibility：Candidate Opportunity
- Battery Recognition：High Attention Risk
- Mechanical Tolerance：High Attention Risk
- Lithium SKU：Compliance Verification Required

注意：

只有证据足够才能展示为 Confirmed。

------

## Top User Pain Points

VOC 排名。

------

## Top Risks

风险矩阵。

------

## Product Gates

Market
Product
Technical
Manufacturing
Financial

------

## Final Decision

例如：

CONDITIONAL GO

下面展示理由。

------

# 十八、风险矩阵 UI

展示：

Risk
Stage
Severity
Evidence Status
Validation
Mitigation

点击 Risk：

打开详细 Risk Card。

这是现场 Demo 的重点。

------

# 十九、数据文件

创建 Demo Dataset。

建议：

data/internal/pen_x1.json

包含当前题目给出的真实信息。

不要增加未知 PEN-X1 参数。

创建：

data/reviews/

thrunite_reviews.csv
streamlight_reviews.csv
nitecore_reviews.csv
weltool_reviews.csv

如果没有真实 Review：

使用：

SAMPLE_DEMO_REVIEW

并在 UI 明确标记。

不要伪装真实数据。

------

# 二十、Seed Data 原则

Seed 数据分：

FACT

题目明确给出的信息。

PUBLIC_FIXTURE

公开竞品示例数据。

SAMPLE

为了演示流程生成的评论样例。

SCENARIO

利润测试中的价格 / 退货率。

界面必须让人看得出这些数据性质。

------

# 二十一、API

设计至少：

GET /api/project

POST /api/analysis/run

GET /api/analysis/{run_id}

GET /api/analysis/{run_id}/skills

GET /api/analysis/{run_id}/skills/{skill_id}

GET /api/analysis/{run_id}/facts

GET /api/analysis/{run_id}/evidence

GET /api/analysis/{run_id}/risks

GET /api/analysis/{run_id}/report

POST /api/profit/calculate

可以根据实际项目简化。

------

# 二十二、执行方式

点击：

Run Analysis

Backend：

生成 run_id

依次运行 Skill。

每运行一个 Skill：

记录：

skill_id
status
started_at
finished_at
input_summary
output_summary
warnings
error

前端实时刷新进度。

第一版：

Polling 即可。

不需要为了 Demo 上 WebSocket。

------

# 二十三、错误处理

任何 Skill 失败：

不能整个流程白屏。

例如：

VOC 分析失败。

状态：

FAILED

下游如果还能运行：

使用已有数据继续。

否则：

SKIPPED

最终报告注明：

“VOC 数据不足，因此市场机会置信度降低。”

这正好体现真实 Agent 的容错能力。

------

# 二十四、日志

后端至少打印：

run_id
skill
status
duration
model
token usage（如果 SDK 可获取）
error

不要打印：

API Key
完整敏感环境变量

------

# 二十五、测试要求

必须写测试。

至少：

## Unit Tests

Fact Status

Profit Calculator

Risk Score

Opportunity Evidence Rule

SWOT Evidence Binding

Report Validator

## Integration Test

跑一次完整 DEMO_MODE：

Skill 01 → Skill 10

必须最终：

生成 AnalysisState
生成 Report
Validation 完成

测试中不调用真实 OpenAI。

------

# 二十六、README

必须创建完整 README.md。

包含：

项目介绍

架构图

10 Skill

数据流

数据来源

防幻觉

风险识别

如何运行

DEMO_MODE

REAL_MODE

截图位置预留

面试演示步骤

------

# 二十七、面试 Demo Script

创建：

docs/demo-script.md

帮我准备一个 5～8 分钟演示流程。

建议：

第 1 分钟：
介绍为什么不是普通 ChatBot。

第 2 分钟：
点击 Run，展示 10 Skill。

第 3 分钟：
展示市场 / 竞品 / VOC。

第 4 分钟：
展示 Opportunity 的证据链。

第 5 分钟：
重点讲“五电池兼容”风险。

第 6 分钟：
展示研发 → 量产 → Amazon 风险。

第 7 分钟：
展示利润与 Gate。

第 8 分钟：
展示 CONDITIONAL GO + 最终报告 + Validator。

------

# 二十八、不要做的事情

不要：

1. 编造 PEN-X1 流明
2. 编造续航
3. 编造 IP 等级
4. 编造真实 Amazon 销量
5. 编造真实 Review 数量
6. 声称分析几千条 Amazon Review
7. 让 LLM 算利润
8. 一个 Prompt 完成全部分析
9. 为了 UI 好看隐藏 UNKNOWN
10. 风险没有验证措施
11. 风险没有解决方案
12. 所有 Gate 默认 PASS
13. API Key 写死
14. 前端直接调用 OpenAI API
15. 一开始开发 Amazon 大规模爬虫

------

# 二十九、代码质量要求

要求：

- 类型明确
- 函数职责单一
- Pydantic Schema
- 不写巨大 God File
- 不写巨大 if/else Workflow
- Skill 可以独立测试
- Provider 可以替换
- Fixture 与 Production Data 分开
- 使用合理异常处理
- README 可读
- 不过度工程化

------

# 三十、开发执行顺序

现在不要无计划地直接堆页面。

请按下面顺序执行。

## Phase 0：检查当前仓库

先阅读：

- 当前目录
- README
- package config
- Python config
- git 状态
- 已存在代码

如果已有项目：

优先复用。

不要无理由重建。

------

## Phase 1：先输出实施计划

创建：

docs/implementation-plan.md

列出：

项目目录
数据模型
10 Skill
API
前端页面
测试
开发顺序

计划完成后继续实施，不需要等我逐项确认。

------

## Phase 2：后端基础架构

完成：

FastAPI
Config
Pydantic
AnalysisState
Fact
Evidence
RiskCard
SkillResult
LLM Provider

------

## Phase 3：实现 DEMO_MODE

这是最高优先级。

确保：

完全不依赖外网也能跑完整流程。

------

## Phase 4：实现 10 Skill

逐个实现。

每完成一个：

写 Unit Test。

------

## Phase 5：Workflow

串联：

01 → 10。

------

## Phase 6：API

让前端可以调用。

------

## Phase 7：前端

实现投屏 Dashboard。

优先信息表达。

不要过度动画。

------

## Phase 8：报告 + Validator

确保最终报告可查看 Markdown。

------

## Phase 9：全链路测试

启动：

backend
frontend

执行完整 Analysis。

确认：

没有 JS Console error
没有 Backend Traceback
所有 API 返回正常
最终 Report 正常生成

------

# 三十一、完成标准 / Acceptance Criteria

只有全部满足才算完成。

## AC01

项目能够本地启动。

## AC02

没有 OpenAI Key 时：

DEMO_MODE 可以完整运行。

## AC03

有 Key 时：

可以使用 OpenAI Provider。

## AC04

点击 Run Analysis：

10 Skill 按顺序运行。

## AC05

每个 Skill：

都能查看：

Input
Source
Action
Output

## AC06

Fact 有：

Source
Status
Confidence

## AC07

VOC Pain Point：

可追溯原始 Evidence。

## AC08

Opportunity：

至少绑定：

VOC Evidence
Competitor Evidence
Product Capability

证据不足则 NEED_VERIFY。

## AC09

技术风险：

必须包含：

Cause
Impact
Validation
Mitigation

## AC10

完整覆盖：

研发
EVT
DVT
PVT
量产
运输
Amazon 上市
退货

## AC11

利润使用程序计算。

## AC12

SWOT 有 Evidence。

## AC13

最终可以产生：

GO
CONDITIONAL GO
NO_GO

## AC14

Product Gate 可展示。

## AC15

最终生成 Markdown Report。

## AC16

Report Validator 能识别：

Unsupported Claim。

## AC17

没有任何地方虚构 PEN-X1 未提供参数。

## AC18

README 完整。

## AC19

docs/demo-script.md 存在。

## AC20

测试全部通过。

------

# 三十二、最终交付时请自己进行一次完整自检

在告诉我“完成”之前：

1. 安装依赖
2. 运行 backend tests
3. 运行 frontend build
4. 启动应用
5. 跑一次 DEMO_MODE 全链路
6. 检查日志
7. 检查最终报告
8. 检查所有 Skill 状态
9. 检查浏览器 Console
10. 修复发现的问题

不要仅仅因为：

“代码已经写完”

就判断项目完成。

必须用实际运行结果证明。

------

# 三十三、最终向我汇报

全部完成后，用中文简短汇报：

## 1. 完成了什么

## 2. 当前项目目录

## 3. 如何启动

## 4. DEMO_MODE 如何运行

## 5. REAL_MODE 如何配置

## 6. 已完成测试

## 7. 当前还存在什么限制

## 8. 面试现场推荐如何演示

另外列出：

- 主要文件
- 主要 API
- 10 个 Skill 对应代码位置

不要只告诉我：

“已完成”。

我要能够立刻启动并验证。

# 重要补充：模型与测试执行策略调整

以下要求优先级高于前文中对应的 OpenAI 和测试要求，请按本节执行。

------

# 一、大模型 API 改为 DeepSeek

当前开发环境使用 DeepSeek API。

环境变量统一使用：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

不要要求我提供：

```text
OPENAI_API_KEY
```

也不要把任何 API Key 写死在代码中。

后端仍然必须设计统一的 LLM Provider 抽象层，例如：

```text
backend/app/llm/
├── base.py
├── deepseek_provider.py
└── mock_provider.py
```

业务 Skill 不允许直接依赖 DeepSeek SDK。

调用关系必须是：

```text
Skill
↓
LLMProvider
↓
DeepSeekProvider
↓
DeepSeek API
```

这样后续如果需要替换为 OpenAI、Claude、Gemini 等海外模型，只需要新增 Provider，不修改 10 个 Skill 的业务逻辑。

------

# 二、当前默认模型模式

支持两种模式。

## REAL_MODE

如果存在：

```text
DEEPSEEK_API_KEY
```

则使用 DeepSeek API。

主要用于：

- VOC 评论语义分类
- 评论痛点归一化
- 市场机会推理
- 风险原因分析
- 风险解决方案生成
- SWOT
- 报告生成

具体模型名称从：

```text
DEEPSEEK_MODEL
```

读取。

不要硬编码。

------

## DEMO_MODE

如果：

```text
DEMO_MODE=true
```

或者 DeepSeek API 不可用：

使用：

```text
MockLLMProvider
```

保证整个 Agent Workflow 仍可以完整运行。

现场演示不能因为模型 API 网络异常直接失败。

------

# 三、模型使用边界

DeepSeek 负责语义理解和推理。

但以下内容禁止交给大模型直接计算：

- 利润
- 百分比统计
- Review Frequency
- Risk Score
- 排名计算
- 数值聚合
- 数据去重

这些使用 Python 完成。

整体保持：

```text
原始数据
↓
Python 数据处理
↓
DeepSeek 语义分析
↓
Pydantic Structured Output
↓
业务规则校验
↓
结构化结果
```

禁止：

```text
把所有数据直接扔给 DeepSeek
↓
让模型自由生成完整报告
```

------

# 四、不要在开发过程中频繁跑全量测试

这是本次开发的重要执行要求。

目标：

优先快速完成完整 Demo。

不要出现：

```text
修改一个文件
→ pytest 全量

修改一个 Skill
→ pytest 全量

修改前端
→ npm build

再修改一个文件
→ 再跑全量
```

禁止无意义重复执行耗时测试。

------

# 五、开发阶段测试策略

开发过程中采用：

## 最小验证

只在确实有必要时执行：

### Python

```text
语法检查
import 检查
关键模块能否启动
```

### Backend

关键接口完成后可以进行一次简单 Smoke：

```text
FastAPI 是否启动
接口是否能返回
```

### Frontend

开发过程中只需要保证：

```text
页面能启动
明显的 TypeScript / import 错误及时修复
```

不要频繁执行：

```text
npm run build
```

------

# 六、不要每完成一个 Skill 都运行完整测试

之前：

```text
Skill 01
→ Unit Test

Skill 02
→ Unit Test

Skill 03
→ Unit Test
```

修改为：

```text
Skill 01
Skill 02
Skill 03
Skill 04
Skill 05
Skill 06
Skill 07
Skill 08
Skill 09
Skill 10
        ↓
Workflow
        ↓
API
        ↓
Frontend
        ↓
全部开发基本完成
        ↓
统一测试
```

可以先写测试文件。

但开发过程中：

**不要求每写完一个模块立即执行测试。**

------

# 七、最终统一测试阶段

只有主体功能全部开发完成后，再进入：

```text
FINAL VERIFICATION
```

这时统一执行完整验证。

顺序：

## Step 1

安装 / 检查依赖。

## Step 2

运行 Backend Test Suite。

例如：

```text
pytest
```

## Step 3

修复 Backend 测试问题。

## Step 4

运行 Frontend Build。

例如：

```text
npm run build
```

## Step 5

修复 TypeScript / Build 问题。

## Step 6

启动 Backend。

## Step 7

启动 Frontend。

## Step 8

执行一次完整：

```text
DEMO_MODE
```

全链路：

```text
资料检查
↓
市场调研
↓
竞品分析
↓
VOC
↓
机会分析
↓
技术风险
↓
研发/量产/上市风险
↓
利润分析
↓
SWOT
↓
最终报告
↓
Validator
```

## Step 9

再执行一次 REAL_MODE。

前提：

```text
DEEPSEEK_API_KEY
```

可用。

至少验证一次真实模型调用成功。

## Step 10

检查：

- Backend traceback
- Frontend console error
- API error
- Skill FAILED
- Report 是否正常
- Evidence 是否可追踪
- UNKNOWN 是否被错误补全
- Profit 是否使用 Python 计算
- Risk 是否包含 Validation + Mitigation

------

# 八、测试失败处理原则

第一次完整测试如果出现多个问题：

不要看到一个错误就立刻反复重新运行整个测试套件。

应该：

```text
运行一次
↓
收集全部失败项
↓
分析共同根因
↓
批量修复
↓
再次运行
```

例如：

第一次：

```text
12 failed
```

不要：

```text
修第 1 个
→ pytest

修第 2 个
→ pytest

修第 3 个
→ pytest
```

应该：

```text
分析 12 个失败
↓
分类
↓
一起修复
↓
重新 pytest
```

减少重复执行。

------

# 九、最终目标优先级

本项目不是为了追求：

```text
100% 测试覆盖率
```

而是为了保证：

```text
完整 Agent Workflow
+
面试现场稳定 Demo
+
Skill 边界清晰
+
数据来源可解释
+
Evidence 可追踪
+
防幻觉
+
风险识别完整
+
最终成品报告可展示
```

优先级：

```text
P0：Demo 可以完整运行
P0：10 Skill 全链路
P0：最终报告生成
P0：风险分析可展示

P1：真实 DeepSeek 调用
P1：Evidence / Fact / Risk 可追踪
P1：错误降级

P2：测试覆盖率
P2：UI 微调
P3：工程化扩展
```

不要为了提高测试覆盖率影响 Demo 主流程的完成。

------

# 十、开发完成前禁止提前宣布完成

全部代码写完后：

必须进入一次：

```text
FINAL VERIFICATION
```

只有完成：

```text
Backend Test
+
Frontend Build
+
DEMO_MODE Full Workflow
+
REAL_MODE DeepSeek Smoke
```

并确认主要流程没有阻塞性问题后，才可以告诉我：

```text
项目开发完成
```

最终汇报时明确告诉我：

1. Backend Test 结果
2. Frontend Build 结果
3. DEMO_MODE 结果
4. DeepSeek REAL_MODE 是否验证
5. 当前剩余问题
6. 面试现场推荐启动方式

# 补充强制要求：开发环境、模型、技术栈与执行策略

以下要求优先级高于前文中与之冲突的内容。

如果前文出现 OpenAI、venv、Docker、频繁单元测试等要求，以本节为最终标准。

------

# 1. 项目名称

项目名称固定为：

```text
pen-x1-product-analyst-agent
```

项目定位：

```text
PEN-X1 手电筒产品分析师 AI Agent 面试演示 Demo
```

不要扩展成通用 SaaS 平台。

------

# 2. 项目根目录

项目根目录：

```text
D:\Projects\pen-x1-product-analyst-agent
```

所有新增和修改操作只能发生在该目录及其子目录中。

禁止修改：

- D:\Projects 下其他项目
- 用户 Desktop
- Documents
- Downloads
- 其他 Git 仓库
- 其他 Python 项目
- 其他 Node 项目
- 系统配置文件

如果该目录已经存在项目文件：

先检查和理解现有内容。

不要直接删除后重建。

------

# 3. 最终技术栈固定

## 前端

```text
React
TypeScript
Vite
Tailwind CSS
npm
```

可使用轻量 UI 组件库。

不要为了界面引入大型复杂框架。

------

## 后端

```text
Python 3.11
FastAPI
Pydantic v2
```

------

## Agent 编排

优先：

```text
LangGraph
```

但原则是：

LangGraph 用于明确表达 Skill Workflow，而不是为了“用了 LangGraph”增加复杂度。

如果部分确定性步骤更适合普通 Python Service：

直接使用 Python。

整体可以是：

```text
LangGraph / Workflow
        ↓
Skill
        ↓
Service / Provider
```

------

## 大模型

当前真实模型：

```text
DeepSeek API
```

通过统一：

```text
LLMProvider
```

封装。

------

## 数据处理

```text
Python
Pandas
```

用于：

- CSV 处理
- 评论统计
- 数据清洗
- 去重
- Frequency 计算
- 利润计算
- 数值聚合

------

## 数据存储

第一版只允许：

```text
SQLite
JSON
CSV
```

不需要大型数据库。

------

## 最终报告

```text
Markdown
```

系统最终应生成：

```text
PEN-X1 北美市场产品调研与上市可行性分析报告.md
```

------

# 4. 禁止 Docker

本项目禁止使用 Docker。

即使电脑已经安装 Docker，也不要使用。

禁止：

```text
docker run
docker compose
docker build
```

禁止：

- 新建 Docker Container
- 新建 Docker Image
- 新建数据库容器
- 修改已有 Docker Container
- 重启其他项目 Docker 服务
- 使用其他项目现有 Docker 环境

项目必须完全能够在 Windows 本机环境直接运行。

------

# 5. 不使用以下基础设施

当前 Demo 禁止主动引入：

```text
Redis
PostgreSQL
MySQL
MongoDB
Milvus
Elasticsearch
Kafka
RabbitMQ
Celery
Kubernetes
Nginx
```

除非后续我明确要求。

不要把一个面试 Demo 做成生产级微服务架构。

------

# 6. Python 环境统一使用 Conda

当前电脑已经安装 Conda。

本项目不要创建：

```text
.venv
venv
virtualenv
```

不要出现：

```text
Conda + venv
```

双重虚拟环境。

------

# 7. Conda 环境名称

项目独立 Conda 环境统一命名：

```text
pen-x1-agent
```

Python：

```text
3.11
```

开发前首先检查：

```text
conda env list
```

如果：

```text
pen-x1-agent
```

已经存在：

检查 Python 版本和环境状态后复用。

如果不存在：

创建：

```text
conda create -n pen-x1-agent python=3.11
```

然后：

```text
conda activate pen-x1-agent
```

------

# 8. 禁止使用 Conda base 环境开发

不要直接在：

```text
base
```

环境安装本项目依赖。

所有 Backend Python 依赖必须安装在：

```text
pen-x1-agent
```

中。

禁止：

- 删除其他 Conda 环境
- 修改其他 Conda 环境
- conda clean --all
- 修改全局 Conda channel
- 升级其他项目 Python
- 修改 Conda 全局配置

------

# 9. Python 依赖要求

后端维护：

```text
backend/requirements.txt
```

或者：

```text
pyproject.toml
```

优先保持简单。

不要同时维护多套互相冲突的依赖系统。

执行 pip 之前确认：

```text
python --version
where python
```

确认当前 Python 来自：

```text
pen-x1-agent
```

环境。

不要：

```text
pip install --user
```

不要往系统 Python 安装依赖。

不要无差别：

```text
pip install --upgrade ...
```

升级整个环境。

------

# 10. Node.js 环境

前端建议：

```text
Node.js 20 LTS
npm
```

如果电脑已有兼容 Node 环境：

直接使用。

不要主动升级系统 Node。

不要全局安装大量 npm 包。

所有依赖必须限制在：

```text
frontend/node_modules
```

中。

如果当前项目没有使用 pnpm / yarn：

不要自行切换包管理器。

------

# 11. DeepSeek API 配置

不要使用：

```text
OPENAI_API_KEY
```

当前真实模型 API 使用：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

配置文件：

```text
.env
```

示例文件：

```text
.env.example
```

例如：

```text
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=
DEMO_MODE=true
```

`.env` 必须加入：

```text
.gitignore
```

------

# 12. API Key 安全要求

禁止：

- API Key 写死在 Python
- API Key 写到 TypeScript
- API Key 写入 README
- API Key 写入 Fixture
- API Key 写入测试
- API Key 提交 Git

DeepSeek 只能由 Backend 调用。

架构：

```text
React
  ↓
FastAPI
  ↓
LLMProvider
  ↓
DeepSeekProvider
  ↓
DeepSeek API
```

绝对禁止：

```text
React
↓
DeepSeek API
```

------

# 13. LLM Provider 必须解耦

建议：

```text
backend/app/llm/
├── base.py
├── deepseek_provider.py
└── mock_provider.py
```

Skill 不允许直接调用 DeepSeek SDK。

统一：

```text
Skill
↓
LLMProvider
```

这样未来如需切换：

- OpenAI
- Claude
- Gemini

只需要增加 Provider。

不要重写 10 个 Skill。

------

# 14. 关于题目“海外大模型”的兼容说明

当前开发环境暂时使用：

```text
DeepSeek API
```

但系统架构必须保持模型无关。

README 中可以说明：

```text
当前 Demo Provider 使用 DeepSeek，
Agent Workflow、Skill、Schema、Evidence、Validator
均与具体模型解耦，
可替换为 OpenAI / Claude / Gemini Provider。
```

不要在代码中把整个业务逻辑与 DeepSeek 强绑定。

------

# 15. 必须支持 REAL_MODE 与 DEMO_MODE

## REAL_MODE

存在有效：

```text
DEEPSEEK_API_KEY
```

时，可以调用 DeepSeek。

用于：

- VOC 语义分类
- Pain Point 归一化
- Opportunity 分析
- Risk 分析
- SWOT
- 报告语言生成

------

## DEMO_MODE

配置：

```text
DEMO_MODE=true
```

时：

使用：

```text
MockLLMProvider
```

不依赖：

- DeepSeek
- 外网
- Amazon API
- 第三方付费 API

依然可以完整跑通 10 Skill。

这是面试现场的兜底模式。

------

# 16. LLM 不能负责确定性计算

DeepSeek 负责：

```text
语义理解
分类
归纳
推理
文本生成
```

Python 负责：

```text
评论次数
Frequency
比例
排序
数据去重
利润
退货率敏感性
Risk Score
数据聚合
```

禁止：

```text
让 DeepSeek 自己心算利润
```

或者：

```text
让 DeepSeek 自己估算评论比例
```

整体流程：

```text
Raw Data
↓
Python Preprocessing
↓
DeepSeek Semantic Analysis
↓
Pydantic
↓
Business Validation
↓
Structured Result
```

------

# 17. 数据库策略

当前版本优先：

```text
SQLite
```

如果第一版甚至不需要关系型数据库：

也可以使用：

```text
JSON + CSV + In-Memory Run State
```

优先保证 Demo 简单稳定。

不要因为“未来扩展”提前上 PostgreSQL。

------

# 18. 数据来源必须明确分类

所有数据必须标记数据性质。

至少区分：

```text
FACT
PUBLIC_FIXTURE
SAMPLE
SCENARIO
UNKNOWN
```

其中：

## FACT

题目明确给出的：

- PEN-X1 五电池方案
- $34.95
- BOM 48.6 / 57.6
- BOOST
- 电池识别
- 机械补偿
- 目标用户

## PUBLIC_FIXTURE

整理后的公开竞品数据。

## SAMPLE

为了演示 VOC Workflow 使用的示例评论。

必须明确标记：

```text
SAMPLE / DEMO
```

不能冒充真实 Amazon 全量评论。

## SCENARIO

例如：

- $29.95
- $32.95
- $34.95
- $36.95
- $39.95

以及：

- 3%
- 5%
- 8%
- 10%
- 15%

这些是利润敏感性测试场景。

不能写成市场事实。

------

# 19. 不开发 Amazon 大规模爬虫

第一版不要花时间实现：

- Amazon 全站爬虫
- 反爬系统
- Proxy Pool
- Captcha
- Browser Automation

VOC 第一版：

```text
CSV Import
```

即可。

市场和竞品数据：

先使用 Fixture Provider。

后续架构中预留：

```text
AmazonProvider
KeepaProvider
Helium10Provider
JungleScoutProvider
```

但当前不要求真实接入。

------

# 20. Skill 流程保持固定

主体仍按照：

```text
01 资料完整性检查
↓
02 市场调研
↓
03 竞品分析
↓
04 Amazon VOC
↓
05 市场机会
↓
06 产品技术风险
↓
07 研发 / 量产 / 海外上市风险
↓
08 价格利润
↓
09 SWOT / Product Decision
↓
10 最终报告
↓
Independent Validator
```

不要为了代码方便合并成：

```text
一个 Prompt
```

也不要为了“Agent 感”拆成几十个无意义 Agent。

------

# 21. LangGraph 使用原则

如果使用 LangGraph：

State 统一使用：

```text
AnalysisState
```

Node 对应主要 Skill。

不要把所有业务规则塞进 Graph Node。

应该：

```text
LangGraph Node
↓
Skill
↓
Service
↓
Provider
```

Graph 主要负责：

- 顺序
- 状态
- 条件分支
- Failed / Skipped
- Validator Return

------

# 22. 不需要实时 WebSocket

前端获取 Skill 状态：

第一版使用：

```text
Polling
```

即可。

例如：

```text
每 1 秒请求 Analysis Run Status
```

不要为了实时性增加：

- WebSocket
- Redis PubSub
- SSE Infrastructure

如果普通 Polling 已经满足现场演示：

就不要过度开发。

------

# 23. 默认运行端口

Frontend：

```text
5173
```

Backend：

```text
8000
```

默认：

```text
http://localhost:5173
http://localhost:8000
```

------

# 24. 端口冲突处理

启动前检查端口。

如果：

```text
5173
8000
```

被其他程序占用：

禁止直接杀掉来源不明的进程。

不要执行：

```text
taskkill /F
Stop-Process
kill
```

除非该进程明确是本次项目由你启动的。

如果不是本项目：

临时切换：

```text
Frontend 5174
Backend 8001
```

并在最终汇报中说明。

------

# 25. 禁止修改系统级环境

不要修改：

- Windows Registry
- 系统 PATH
- Hosts
- Firewall
- DNS
- Windows Service
- PowerShell Execution Policy
- 系统 Proxy
- 全局 npm 配置
- 全局 Git 配置

如果遇到系统环境问题：

报告给我。

不要擅自做高风险系统修改。

------

# 26. 不要求管理员权限

项目应该尽量以：

```text
普通 Windows 用户权限
```

运行。

不要默认要求：

```text
Run as Administrator
```

------

# 27. Git 安全要求

当前项目允许正常：

```text
git init
git status
git add
git commit
```

但是不要执行：

```text
git reset --hard
git clean -fd
git clean -fdx
```

不要通过删除用户文件来解决 Git 问题。

------

# 28. 不要频繁重新安装依赖

首次：

```text
pip install -r requirements.txt
npm install
```

之后：

只有依赖文件发生变化才重新安装。

禁止每轮代码修改都执行：

```text
pip install ...
npm install
```

------

# 29. 测试策略：先完成主体，再统一测试

这是本项目的重要执行要求。

不要：

```text
写一个函数
→ pytest

写一个 Skill
→ pytest

修改前端
→ npm build

再改一个 Skill
→ pytest
```

不要频繁跑全量测试。

当前目标是：

```text
先把完整 Demo 主流程实现
↓
最后集中验证
```

------

# 30. 开发期间允许的最小检查

开发过程中，如果需要，可以执行：

- Python syntax check
- import check
- 单个关键函数 smoke
- FastAPI 能否启动
- React dev server 能否启动
- 明显 TypeScript 编译错误检查

但不要反复执行完整：

```text
pytest
npm run build
```

------

# 31. 推荐实际开发顺序

按以下顺序优先完成：

```text
项目骨架
↓
Pydantic Schemas
↓
AnalysisState
↓
Fact / Evidence / Risk Model
↓
DeepSeekProvider / MockProvider
↓
DEMO_MODE
↓
10 Skills
↓
Workflow
↓
API
↓
Frontend Dashboard
↓
Report Generator
↓
Validator
↓
README
↓
Demo Script
↓
FINAL VERIFICATION
```

先把链路做完整。

不要局部打磨太久。

------

# 32. 测试文件可以边开发边写，但暂时不频繁运行

可以同步创建：

```text
tests/
```

尤其覆盖：

- Profit Calculator
- Risk Score
- Opportunity Evidence Rule
- Fact Status
- Report Validator
- DEMO Workflow

但开发主体完成前：

不要求每新增测试都立即运行。

------

# 33. FINAL VERIFICATION

主体开发完成以后：

统一执行一次完整验证。

顺序如下。

## Step 1

确认：

```text
conda activate pen-x1-agent
```

以及：

```text
python --version
```

------

## Step 2

运行 Backend 完整测试：

```text
pytest
```

------

## Step 3

如果出现多个失败：

先完整收集错误。

不要：

```text
修一个
→ pytest

修一个
→ pytest
```

而是：

```text
收集失败
↓
分类
↓
找共同根因
↓
批量修复
↓
再次 pytest
```

------

## Step 4

运行：

```text
npm run build
```

处理：

- TypeScript
- Vite
- import
- build

问题。

------

## Step 5

启动 Backend。

------

## Step 6

启动 Frontend。

------

## Step 7

执行一次完整：

```text
DEMO_MODE
```

验证：

```text
Skill 01
↓
Skill 02
↓
Skill 03
↓
Skill 04
↓
Skill 05
↓
Skill 06
↓
Skill 07
↓
Skill 08
↓
Skill 09
↓
Skill 10
↓
Validator
```

------

## Step 8

检查：

- 是否生成最终 Markdown Report
- Skill 是否异常 FAILED
- Backend 是否有 Traceback
- Frontend 是否白屏
- Browser Console 是否有阻塞错误
- Evidence 是否可打开
- UNKNOWN 是否被错误补全
- Opportunity 是否有 Evidence
- Risk 是否有 Validation + Mitigation
- Profit 是否来自 Python
- Product Gate 是否正确展示

------

## Step 9

如果 DeepSeek API 配置有效：

再做一次轻量：

```text
REAL_MODE Smoke Test
```

只需证明：

- Provider 能连接
- Structured Output 正常
- 至少关键 LLM Skill 可以成功调用

不要为了 REAL_MODE 再跑大量重复测试。

------

# 34. 最终测试目标

不是追求：

```text
100% Coverage
```

而是：

```text
面试 Demo 可稳定运行
+
核心业务逻辑正确
+
10 Skill 全链路完成
+
Evidence 可追踪
+
防幻觉机制有效
+
完整风险分析
+
最终报告可生成
```

------

# 35. 开发优先级

## P0

必须完成：

- 项目可启动
- DEMO_MODE
- 10 Skill
- Workflow
- Risk Analysis
- Final Report
- Validator

## P1

应完成：

- DeepSeek REAL_MODE
- Evidence Panel
- Product Gate
- Profit Matrix
- VOC Detail
- Failure Degradation

## P2

有时间优化：

- UI
- 动效
- 更多 Fixture
- 更多测试

## P3

当前不要开发：

- Docker
- Redis
- PostgreSQL
- Kafka
- Celery
- Kubernetes
- 微服务
- Amazon 大规模爬虫
- 用户权限
- 商业 SaaS 功能

------

# 36. UI 定位

这是面试投屏 Demo。

UI 要求：

```text
清晰
专业
信息密度合理
```

而不是：

```text
炫技
大量动画
复杂后台菜单
```

重点突出：

- 10 Skill Pipeline
- Evidence
- VOC
- Opportunity
- Risk
- Product Gate
- Decision
- Final Report

其中：

```text
Risk
```

是重点展示模块。

------

# 37. 最终本地架构

项目最终应保持：

```text
Windows
│
├── Conda
│   └── pen-x1-agent
│       └── Python 3.11
│
├── Frontend
│   └── React + TypeScript + Vite
│
├── Backend
│   ├── FastAPI
│   ├── Pydantic
│   ├── LangGraph / Workflow
│   └── DeepSeekProvider
│
├── Data
│   ├── SQLite
│   ├── JSON
│   └── CSV
│
└── Output
    └── Markdown Report
```

不依赖 Docker。

------

# 38. 项目必须脱离 Codex Session 后仍可运行

禁止形成：

```text
只有当前 Codex Terminal 能运行
```

的状态。

Codex 完成工作并退出后：

我自己打开新的 PowerShell / Terminal，应该可以按照 README：

```text
conda activate pen-x1-agent
```

启动 Backend。

然后：

```text
npm run dev
```

启动 Frontend。

所有必要文件必须真实保存在项目目录。

------

# 39. README 必须写清楚环境要求

README 至少明确：

```text
Python 3.11
Conda
Node.js
npm
DeepSeek API
```

以及：

## 第一次启动

如何创建 / 激活 Conda。

## Backend

如何安装依赖。

## Frontend

如何安装依赖。

## DEMO_MODE

如何启动。

## REAL_MODE

如何配置 DeepSeek。

------

# 40. 最终汇报要求

完成后不要只回复：

```text
Done
```

必须向我报告：

## 开发结果

- 完成的模块
- 10 Skill 状态

## 环境

- Conda 环境
- Python 版本
- Node 版本

## 启动方式

准确命令。

## 测试

- pytest 最终结果
- npm build 最终结果
- DEMO_MODE 全链路结果
- REAL_MODE 是否验证

## 数据

明确哪些是：

- FACT
- PUBLIC_FIXTURE
- SAMPLE
- SCENARIO

## 当前限制

明确哪些功能：

- 当前只是 Fixture
- 尚未接 Amazon API
- 尚未接第三方 Amazon 数据工具

## 面试演示

告诉我推荐的 5～8 分钟演示流程。

------

# 41. 最核心的开发原则

遇到不确定如何实现时，请始终优先：

```text
简单
↓
可运行
↓
可解释
↓
可追踪
↓
可演示
```

而不是：

```text
复杂
↓
生产级
↓
过度工程化
```

这个项目最重要的不是证明用了多少技术。

而是证明：

```text
Agent 能将产品分析任务拆成明确 Skill
+
每个 Skill 有真实数据输入
+
Skill 之间有结构化数据流
+
结论有 Evidence
+
模型不知道时不会瞎编
+
能够真正识别 PEN-X1 从研发到量产到 Amazon 上市的风险
+
最后输出可以支持产品决策的完整报告
```

请严格按照这些原则开发。