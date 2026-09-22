from pathlib import Path
from app.schemas.models import SkillRun, Evidence, Fact
from app.schemas.state import AnalysisState
from app.services.data_loader import load_project_facts
from app.llm.factory import get_llm_provider
from app.data_providers.fixture_provider import FixtureProvider
from app.data_providers.review_csv_provider import ReviewCsvProvider
from app.data_providers.official_site_provider import OfficialWebsiteProvider
from app.data_providers.amazon_snapshot_provider import AmazonSnapshotCompetitorProvider
from app.services.amazon_auth import AmazonSettings
from app.services.amazon_sync import AmazonSyncService
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
    def __init__(self, data_root: Path, output_dir: Path | None = None,
                 amazon_snapshot: dict | None = None, amazon_settings: AmazonSettings | None = None,
                 review_db_path: Path | None = None):
        self.data_root=Path(data_root); self.output_dir=output_dir or self.data_root/'outputs'
        self.amazon_snapshot=amazon_snapshot
        self.amazon_settings=amazon_settings or AmazonSettings.from_environment()
        self.review_db_path=review_db_path
    def run_demo(self) -> AnalysisState: return self.run('DEMO')
    def run(self, mode: str='DEMO') -> AnalysisState:
        mode=mode.upper(); fixture=FixtureProvider(self.data_root); review_provider=ReviewCsvProvider(self.data_root, mode=mode, db_path=self.review_db_path); llm_provider=get_llm_provider(force_real=mode=='REAL')
        market_provider=fixture; competitor_provider=fixture; provider_status={'内部资料':{'status':'READY','source_type':'FACT'}, '市场数据':self._meta(fixture.get_market_data()), '评论数据':self._meta(review_provider.get_reviews())}
        state=AnalysisState(project={'name':'PEN-X1 产品分析师人工智能助手','mode':'REAL_MODE' if mode=='REAL' else 'DEMO_MODE','llm_provider':type(llm_provider).__name__,'data_provider_status':provider_status,'warnings':[]}, facts=list(load_project_facts(self.data_root).values()))
        snapshot=None
        if mode=='REAL':
            snapshot=self._load_amazon_snapshot()
            if snapshot:
                state.facts.extend(Fact.model_validate(item) for item in snapshot.get('facts', []))
                for item in snapshot.get('evidence', []):
                    state.add_evidence(Evidence.model_validate(item))
            self._try_official_sources(state, provider_status)
            competitor_provider=AmazonSnapshotCompetitorProvider(fixture, snapshot or {},
                state.project.get('official_competitors', []))
        self._amazon_status(provider_status, snapshot, mode)
        amazon_feedback=[dict(item, asin=product.get('asin'), brand=product.get('brand'))
                         for product in (snapshot or {}).get('products', [])
                         for item in product.get('feedback', []) if item.get('status')=='LIVE']
        steps=[
          ('01','资料完整性检查',lambda:setattr(state,'market',{'material_check':run_material_check(state)})),
          ('02','市场调研',lambda:setattr(state,'market',state.market|{'research':run_market_research(state,self.data_root,market_provider)})),
          ('03','竞品分析',lambda:setattr(state,'competitors',run_competitor_analysis(state,self.data_root,competitor_provider))),
          ('04','亚马逊用户之声',lambda:setattr(state,'voc',run_voc_analysis(state,self.data_root,llm_provider,mode,review_provider,amazon_feedback))),
          ('05','市场机会',lambda:setattr(state,'opportunities',run_opportunity_analysis(state,llm_provider,mode))),
          ('06','产品技术风险',lambda:setattr(state,'technical_risks',run_technical_risk(state,llm_provider,mode))),
          ('07','研发/量产/上市风险',lambda:setattr(state,'lifecycle_risks',run_lifecycle_risk(state,llm_provider,mode))),
          ('08','价格利润分析',lambda:setattr(state,'profit_analysis',run_profit_analysis(state))),
          ('09','优势劣势机会威胁 / 决策',lambda:self._decision(state,llm_provider,mode)),
          ('10','最终报告',lambda:self._report(state,llm_provider,mode))]
        for skill_id,name,action in steps:
            item=SkillRun(skill_id=skill_id,name=name,status='RUNNING'); state.skill_runs.append(item)
            try:
                action()
                item.status='WARNING' if skill_id=='04' and state.voc.get('status') in {'NEED_DATA','NEED_LLM'} else 'COMPLETED'
                item.message='真实评论不足或语义分析未完成。' if item.status=='WARNING' else '已生成结构化结果。'
            except Exception as error: item.status='FAILED'; item.message=str(error)
        state.validation=validate_report(state); state.report['status']='VALIDATED' if state.validation.passed else 'REVIEW_REQUIRED'
        self.output_dir.mkdir(parents=True,exist_ok=True)
        report_name = 'PEN-X1 Real VOC Smoke Report.md' if mode == 'REAL' else 'PEN-X1 北美市场产品调研与上市可行性分析报告.md'
        (self.output_dir / report_name).write_text(state.report.get('markdown',''),encoding='utf-8')
        return state
    @staticmethod
    def _meta(result): return {'status':result.status,'source_type':result.source_type,'source_name':result.source_name,'source_url':result.source_url,'retrieved_at':result.retrieved_at,'fallback_reason':result.fallback_reason}
    def _load_amazon_snapshot(self):
        if self.amazon_settings.mode!='production' or not self.amazon_settings.real_data_enabled:
            return None
        snapshot=self.amazon_snapshot or AmazonSyncService(self.data_root,self.amazon_settings).latest_snapshot()
        summary=(snapshot or {}).get('summary',{})
        return snapshot if summary.get('mode')=='production' and summary.get('live_records',0)>0 else None
    def _amazon_status(self,provider_status,snapshot,mode):
        summary=(snapshot or {}).get('summary',{})
        configured=self.amazon_settings.configured
        for title,count_field,source_type in [('Amazon Catalog','catalog_records','AMAZON_SP_API'),('Amazon Pricing','pricing_records','AMAZON_SP_API'),('Amazon Customer Feedback','feedback_topics','AMAZON_CUSTOMER_FEEDBACK')]:
            status='LIVE' if mode=='REAL' and summary.get(count_field,0)>0 else ('FALLBACK' if mode=='DEMO' else 'NOT_CONFIGURED' if not configured else 'FALLBACK')
            provider_status[title]={'status':status,'source_type':source_type if status=='LIVE' else 'FIXTURE',
                'source_name':title,'count':summary.get(count_field,0) if status=='LIVE' else 0,
                'retrieved_at':summary.get('finished_at'),'fallback_reason':None if status=='LIVE' else '当前使用演示数据。'}
        provider_status['Amazon SP-API']={'status':'LIVE' if summary.get('live_records',0)>0 else 'NOT_CONFIGURED' if not configured else 'FALLBACK',
            'source_type':'AMAZON_SP_API','source_name':'Amazon SP-API','retrieved_at':summary.get('finished_at')}
        if snapshot:
            provider_status['竞品数据']={'status':'LIVE','source_type':'AMAZON_SP_API',
                'source_name':'Amazon SP-API','retrieved_at':summary.get('finished_at')}
    def _try_official_sources(self,state,provider_status):
        provider=OfficialWebsiteProvider(); results=[provider.get_competitor(*item) for item in OFFICIAL_PRODUCTS]; live=[result for result in results if result.status=='LIVE']
        provider_status['品牌官网']={'status':'LIVE' if live else 'FALLBACK','source_type':'OFFICIAL_SITE' if live else 'FIXTURE','source_name':'品牌官网' if live else '竞品演示数据','retrieved_at':results[0].retrieved_at,'fallback_reason':None if live else '; '.join(result.fallback_reason or '' for result in results)}
        if live:
            state.project['official_competitors']=[result.data for result in live if result.data]
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
