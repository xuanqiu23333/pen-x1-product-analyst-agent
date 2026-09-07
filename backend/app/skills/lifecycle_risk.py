from pydantic import BaseModel, Field
from app.schemas.state import AnalysisState
from app.schemas.models import RiskCard
class LifecycleGuidance(BaseModel): notes: list[str]=Field(default_factory=list)
def run_lifecycle_risk(state: AnalysisState,llm_provider=None,mode: str='DEMO')->list[dict]:
    if mode.upper()=='REAL' and llm_provider is not None:
        try: LifecycleGuidance.model_validate(llm_provider.complete_json('仅返回 JSON：{"notes":["生命周期风险建议"]}。不得编造产品事实。',{'lifecycle':['研发','EVT','DVT','PVT','量产','运输','仓储','亚马逊页面','消费者使用','售后','退货']})); state.project.setdefault('llm_skill_calls',[]).append('生命周期风险')
        except Exception as error: state.project.setdefault('warnings',[]).append(f'生命周期风险的模型补充不可用：{error}')
    cards=[RiskCard(risk_id='eol-compatibility',stage='量产',module='EOL 测试',risk='五电池兼容性不能依赖逐台人工装入每种消费电池。',cause='外形与电气组合多',trigger='产线覆盖缺口',impact='现场兼容性遗漏',severity=4,probability=None,detectability=3,evidence_ids=['ev-project-brief'],validation_method='标准化电池模拟器与极限尺寸治具',mitigation='使用受控治具建立五电池兼容性 EOL 测试',status='NEED_VERIFY'),RiskCard(risk_id='lithium-shipping',stage='运输',module='合规',risk='含 14500 电池的 SKU 需要外部运输合规验证。',cause='锂电运输要求',trigger='含电池 SKU',impact='运输延误或页面限制',severity=5,probability=None,detectability=2,evidence_ids=['ev-project-brief'],validation_method='针对 SKU 和路线开展外部合规审查',mitigation='合规验证前不开放含电池 SKU',status='NEED_VERIFY'),RiskCard(risk_id='listing-clarity',stage='亚马逊上市',module='消费者沟通',risk='消费者可能误解不同电池下的性能差异。',cause='多种供电配置',trigger='页面或说明书不清晰',impact='退货和负面评论',severity=4,probability=None,detectability=3,evidence_ids=['ev-review-str-3'],validation_method='页面理解度测试与客服内容评审',mitigation='提供电池性能对照表与明确安装指引',status='NEED_VERIFY')]
    return [card.model_dump()|{'risk_score':card.risk_score} for card in cards]
