# 5–8 分钟面试演示脚本

1. **定位（30 秒）**：展示顶部的 Amazon US、目标价 $34.95、5 种电池与 DEMO MODE。说明这不是普通聊天机器人，而是一个有 Skill 边界和证据链的产品分析工作流。
2. **启动（30 秒）**：点击“开始分析 PEN-X1”，指出左侧 10 个 Skill 都会保留独立状态。
3. **资料与来源（45 秒）**：选择“资料检查”。强调系统将流明、续航、防水、温升等未给参数保留为 UNKNOWN / NEED_VERIFY，而不是由模型补全。
4. **市场 / 竞品 / VOC（90 秒）**：选择“Amazon VOC”，点击痛点进入右侧 Evidence 面板。说明评论是明确标记的 SAMPLE / DEMO CSV，而非虚构的实时爬虫数据。
5. **机会与风险（2 分钟）**：展示“供电自由度”只能作为推断型机会；然后展示风险矩阵，重点讲电池识别、BOOST、14500 温升、机械公差、EOL 和锂电运输分别都有 Validation 与 Mitigation。
6. **财务与 Gate（75 秒）**：说明价格和退货率是 SCENARIO，利润由 Python 算；Amazon fee、FBA、Freight 等未输入成本保持 UNKNOWN，因此 Financial Gate 为 PENDING。
7. **决策与报告（60 秒）**：展示 CONDITIONAL GO，解释不是硬编码“上市”，而是由技术、量产和财务验证缺口驱动。最后打开报告，说明独立校验器会阻止无证据产品参数进入确定性结论。

## 推荐现场模式

使用 `DEMO_MODE=true`。即使网络或 DeepSeek API 不可用，10 个 Skill、Evidence、风险矩阵、Gate 和 Markdown 报告仍可完整展示。
