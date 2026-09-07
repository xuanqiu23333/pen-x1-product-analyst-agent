from pydantic import BaseModel
from app.schemas.state import AnalysisState
class ReportLanguage(BaseModel): markdown: str
def run_report_generation(state: AnalysisState,llm_provider=None,mode: str='DEMO')->dict:
    lines=['# PEN-X1 北美市场产品调研与上市可行性分析报告','','## 执行摘要','PEN-X1 当前建议为**有条件推进**。报告结论来自结构化 Fact、Evidence、风险、关卡与 Python 计算，未提供参数保持未知或需验证。','','## 数据覆盖说明',f"内部事实：{len(state.facts)} 项；证据：{len(state.evidence)} 条；示例评论：{state.voc.get('review_count',0)} 条；市场数据状态：{state.project.get('data_provider_status',{}).get('市场数据',{}).get('source_type','UNKNOWN')}。",'','## 市场、机会与风险','供电灵活性仅在 VOC、竞品、市场与产品 Fact 同时引用时作为推断型候选机会。电池识别、BOOST、14500 温升、机械公差、EOL 与运输合规仍需验证。','','## 产品关卡与决策']
    for gate in state.decision.get('gates',[]): lines.append(f"- {gate['name']}：**{gate['status']}** —— {gate['reason']}")
    lines += ['','## 后续验证计划','1. 执行按电池配置、品牌、电量、温度和模式划分的兼容性测试。','2. 完成温升、机械接触、EOL、运输合规和页面理解度验证。','3. 补充佣金、FBA、运费和广告等实际成本，重新计算利润。']
    fallback='\n'.join(lines)
    if mode.upper()=='REAL' and llm_provider is not None:
        try:
            generated=ReportLanguage.model_validate(llm_provider.complete_json('仅返回 JSON：{"markdown":"中文报告"}。根据 AnalysisState 写报告，不得增加没有 Fact 或 Evidence 支持的参数。',{'facts':[f.model_dump() for f in state.facts],'decision':state.decision,'validation_rules':'未知内容不可确定性表达'})); state.project.setdefault('llm_skill_calls',[]).append('最终报告'); fallback=generated.markdown or fallback
        except Exception as error: state.project.setdefault('warnings',[]).append(f'报告模型生成不可用：{error}')
    return {'title':'PEN-X1 北美市场产品调研与上市可行性分析报告','status':'DRAFT','markdown':fallback}
