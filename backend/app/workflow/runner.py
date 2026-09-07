from pathlib import Path
from app.schemas.models import SkillRun
from app.schemas.state import AnalysisState
from app.services.data_loader import load_project_facts
from app.llm.factory import get_llm_provider
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

class AnalysisRunner:
    def __init__(self, data_root: Path, output_dir: Path | None = None):
        self.data_root = Path(data_root)
        self.output_dir = output_dir or self.data_root / "outputs"

    def run_demo(self) -> AnalysisState:
        return self.run("DEMO")

    def run(self, mode: str = "DEMO") -> AnalysisState:
        normalized_mode = mode.upper()
        state = AnalysisState(project={"name":"PEN-X1 Product Analyst AI Agent", "mode":"REAL_MODE" if normalized_mode == "REAL" else "DEMO_MODE"}, facts=list(load_project_facts(self.data_root).values()))
        if normalized_mode == "REAL":
            provider = get_llm_provider()
            state.project["llm_provider"] = type(provider).__name__
            state.project["llm_preflight"] = provider.complete_json("Return a JSON object stating the input is ready for structured product analysis.", {"product":"PEN-X1", "constraints":"Do not invent unprovided product specifications."})
        steps = [
            ("01", "资料完整性检查", lambda: setattr(state, "market", {"material_check": run_material_check(state)})),
            ("02", "市场调研", lambda: setattr(state, "market", state.market | {"research": run_market_research(state, self.data_root)})),
            ("03", "竞品分析", lambda: setattr(state, "competitors", run_competitor_analysis(state, self.data_root))),
            ("04", "Amazon VOC", lambda: setattr(state, "voc", run_voc_analysis(state, self.data_root))),
            ("05", "市场机会", lambda: setattr(state, "opportunities", run_opportunity_analysis(state))),
            ("06", "产品技术风险", lambda: setattr(state, "technical_risks", run_technical_risk(state))),
            ("07", "研发/量产/上市风险", lambda: setattr(state, "lifecycle_risks", run_lifecycle_risk(state))),
            ("08", "价格利润分析", lambda: setattr(state, "profit_analysis", run_profit_analysis(state))),
            ("09", "SWOT / Decision", lambda: self._decision(state)),
            ("10", "最终报告", lambda: self._report(state)),
        ]
        for skill_id, name, action in steps:
            item = SkillRun(skill_id=skill_id, name=name, status="RUNNING")
            state.skill_runs.append(item)
            try:
                action(); item.status = "COMPLETED"; item.message = "Structured result generated."
            except Exception as error:
                item.status = "FAILED"; item.message = str(error)
        state.validation = validate_report(state)
        state.report["status"] = "VALIDATED" if state.validation.passed else "REVIEW_REQUIRED"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "PEN-X1 北美市场产品调研与上市可行性分析报告.md").write_text(state.report["markdown"], encoding="utf-8")
        return state

    @staticmethod
    def _decision(state: AnalysisState) -> None:
        state.swot, state.decision = run_swot_decision(state)

    @staticmethod
    def _report(state: AnalysisState) -> None:
        state.report = run_report_generation(state)
