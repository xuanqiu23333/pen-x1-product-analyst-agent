from pydantic import BaseModel, Field
from app.schemas.state import AnalysisState
from app.schemas.models import RiskCard

class RiskGuidance(BaseModel): notes: list[str] = Field(default_factory=list)
def _llm(state, provider, mode, skill):
    if mode.upper()!='REAL' or provider is None: return
    try:
        guidance=RiskGuidance.model_validate(provider.complete_json('请仅返回 JSON：{"notes":["基于已有风险的原因、影响、验证和缓解建议"]}。不得编造概率或产品参数。', {'skill':skill})); state.project.setdefault('llm_skill_calls',[]).append(skill); state.project.setdefault('llm_notes',{})[skill]=guidance.notes
    except Exception as error: state.project.setdefault('warnings',[]).append(f'{skill} 的模型补充不可用：{error}')

def run_technical_risk(state: AnalysisState, llm_provider=None, mode: str='DEMO') -> list[dict]:
    _llm(state,llm_provider,mode,'技术风险')
    risks=[RiskCard(risk_id='battery-identification',stage='产品定义',module='电池识别',risk='AA、AAA 与 14500 在电量、品牌和温度变化时可能出现识别边界重叠。',cause='电压与尺寸边界重叠',trigger='未验证的边界工况',impact='错误模式或输出选择',severity=5,probability=None,detectability=3,evidence_ids=['ev-project-brief'],validation_method='按电池配置 × 品牌 × 电量 × 温度 × 模式执行风险优先测试',mitigation='采用保守识别阈值并建立验证矩阵',status='NEED_VERIFY'),RiskCard(risk_id='boost-stability',stage='EVT',module='BOOST 驱动',risk='宽输入范围可能影响输出稳定性和效率。',cause='输入电压范围宽',trigger='切换电池配置',impact='性能不一致或热负载',severity=4,probability=None,detectability=3,evidence_ids=['ev-project-brief'],validation_method='按配置测量 Vin、Iin、Vout、Iout、效率与温度',mitigation='验证后定义降额与控制边界',status='NEED_VERIFY'),RiskCard(risk_id='thermal-14500',stage='DVT',module='热管理',risk='14500 电池连续高档运行存在潜在温升风险。',cause='更高能量输入',trigger='连续高档使用',impact='舒适度、安全与可靠性问题',severity=5,probability=None,detectability=2,evidence_ids=['ev-project-brief'],validation_method='在项目阈值下测试 30 秒、1 分钟、3 分钟、5 分钟和 10 分钟',mitigation='在项目阈值定义后设置热降档',status='NEED_VERIFY'),RiskCard(risk_id='mechanical-tolerance',stage='PVT',module='机械补偿',risk='电池长度和直径公差可能降低接触一致性。',cause='电芯差异、弹簧压缩与公差叠加',trigger='跌落、振动或磨损',impact='间歇性断电',severity=4,probability=None,detectability=3,evidence_ids=['ev-project-brief'],validation_method='极限尺寸治具、跌落、振动与接触电阻测试',mitigation='通过极限量规验证弹簧力和接触结构',status='NEED_VERIFY')]
    return [risk.model_dump()|{'risk_score':risk.risk_score} for risk in risks]
