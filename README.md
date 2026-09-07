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