from pathlib import Path
from app.schemas.models import SkillRun, Evidence, Fact
from app.schemas.state import AnalysisState
from app.services.data_loader import load_project_facts
from app.llm.factory import get_llm_provider
from app.data_providers.fixture_provider import FixtureProvider
from app.data_providers.review_csv_provider import ReviewCsvProvider
from app.data_providers.official_site_provider import OfficialWebsiteProvider
from app.skills.material_check import run_material_check
from app.skills.market_research import run_market_research
from app.skills.competitor_analysis import run_competitor_analysis
from app.skills.voc_analysis import run_voc_analysis
from app.skills.opportunity_analysis import run_opportunity_analysis
from app.skills.technical_risk import run_technical_risk
from app.skills.lifecycle_risk import run_lifecycle_risk
from app.skills.profit_analysis import run_profit_analysis
from app.skills.swot_decision import run_swot_decision
from app.skills.report_generation import run_report_generation
from app.validators.report_validator import validate_report

OFFICIAL_PRODUCTS = [('ThruNite','Archer 2A C','https://www.thrunite.com/archer-2a-c/'), ('Streamlight','MicroStream','https://www.streamlight.com/products/detail/microstream-usb'), ('Nitecore','MT2A Pro','https://flashlight.nitecore.com/product/mt2apro'), ('Weltool','T1 Pro','https://www.weltool.com/')]

class AnalysisRunner:
    def __init__(self, data_root: Path, output_dir: Path | None = None):
        self.data_root=Path(data_root); self.output_dir=output_dir or self.data_root/'outputs'
    def run_demo(self) -> AnalysisState: return self.run('DEMO')
    def run(self, mode: str='DEMO') -> AnalysisState:
        mode=mode.upper(); fixture=FixtureProvider(self.data_root); review_provider=ReviewCsvProvider(self.data_root); llm_provider=get_llm_provider(force_real=mode=='REAL')
        market_provider=fixture; competitor_provider=fixture; provider_status={'内部资料':{'status':'READY','source_type':'FACT'}, '市场数据':self._meta(fixture.get_market_data()), '评论数据':self._meta(review_provider.get_reviews())}
        state=AnalysisState(project={'name':'PEN-X1 产品分析师人工智能助手','mode':'REAL_MODE' if mode=='REAL' else 'DEMO_MODE','llm_provider':type(llm_provider).__name__,'data_provider_status':provider_status,'warnings':[]}, facts=list(load_project_facts(self.data_root).values()))
        if mode=='REAL': self._try_official_sources(state, provider_status)
        steps=[
          ('01','资料完整性检查',lambda:setattr(state,'market',{'material_check':run_material_check(state)})),
          ('02','市场调研',lambda:setattr(state,'market',state.market|{'research':run_market_research(state,self.data_root,market_provider)})),
          ('03','竞品分析',lambda:setattr(state,'competitors',run_competitor_analysis(state,self.data_root,competitor_provider))),
          ('04','亚马逊用户之声',lambda:setattr(state,'voc',run_voc_analysis(state,self.data_root,llm_provider,mode,review_provider))),
          ('05','市场机会',lambda:setattr(state,'opportunities',run_opportunity_analysis(state,llm_provider,mode))),
          ('06','产品技术风险',lambda:setattr(state,'technical_risks',run_technical_risk(state,llm_provider,mode))),
          ('07','研发/量产/上市风险',lambda:setattr(state,'lifecycle_risks',run_lifecycle_risk(state,llm_provider,mode))),
          ('08','价格利润分析',lambda:setattr(state,'profit_analysis',run_profit_analysis(state))),
          ('09','优势劣势机会威胁 / 决策',lambda:self._decision(state,llm_provider,mode)),
          ('10','最终报告',lambda:self._report(state,llm_provider,mode))]
        for skill_id,name,action in steps:
            item=SkillRun(skill_id=skill_id,name=name,status='RUNNING'); state.skill_runs.append(item)
            try: action(); item.status='COMPLETED'; item.message='已生成结构化结果。'
            except Exception as error: item.status='FAILED'; item.message=str(error)
        state.validation=validate_report(state); state.report['status']='VALIDATED' if state.validation.passed else 'REVIEW_REQUIRED'
        self.output_dir.mkdir(parents=True,exist_ok=True); (self.output_dir/'PEN-X1 北美市场产品调研与上市可行性分析报告.md').write_text(state.report.get('markdown',''),encoding='utf-8')
        return state
    @staticmethod
    def _meta(result): return {'status':result.status,'source_type':result.source_type,'source_name':result.source_name,'source_url':result.source_url,'retrieved_at':result.retrieved_at,'fallback_reason':result.fallback_reason}
    def _try_official_sources(self,state,provider_status):
        provider=OfficialWebsiteProvider(); results=[provider.get_competitor(*item) for item in OFFICIAL_PRODUCTS]; live=[result for result in results if result.status=='LIVE']
        provider_status['品牌官网']={'status':'LIVE' if live else 'FALLBACK','source_type':'OFFICIAL_SITE' if live else 'FIXTURE','source_name':'品牌官网' if live else '竞品演示数据','retrieved_at':results[0].retrieved_at,'fallback_reason':None if live else '; '.join(result.fallback_reason or '' for result in results)}
        if live:
            fixture_rows=FixtureProvider(self.data_root).get_competitor_data().data or []
            for result in live:
                item=result.data or {}; key=f"ev-official-{item['brand'].lower()}-{item['model'].lower().replace(' ','-')}"
                state.add_evidence(Evidence(id=key,source=result.source_name,content=f"官网公开商品页：{item.get('product_name')}",data_nature='PUBLIC_DATA',confidence='MEDIUM',source_url=result.source_url,source_type=result.source_type,retrieved_at=result.retrieved_at))
                price=item.get('price'); fixture=next((row for row in fixture_rows if row['brand']==item['brand'] and row['model']==item['model']),None)
                if price:
                    state.facts.append(Fact(id=f"official-{item['brand'].lower()}-{item['model'].lower().replace(' ','-')}-price",category='competitor',name=f"{item['brand']} {item['model']} 官网标价",value=price,source_type='L2_OFFICIAL',source_name=result.source_name,source_url=result.source_url,status='CONFLICT' if fixture and str(fixture.get('price')) not in price else 'CONFIRMED',confidence='MEDIUM',data_nature='PUBLIC_DATA'))
        else: state.project['warnings'].append('品牌官网当前不可用，已降级使用竞品演示数据。')
    @staticmethod
    def _decision(state,llm_provider,mode): state.swot,state.decision=run_swot_decision(state,llm_provider,mode)
    @staticmethod
    def _report(state,llm_provider,mode): state.report=run_report_generation(state,llm_provider,mode)
