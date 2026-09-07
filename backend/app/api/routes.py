from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.workflow.runner import AnalysisRunner

router = APIRouter(prefix="/api")
RUNS: dict[str, dict] = {}
DATA_ROOT = Path(__file__).resolve().parents[3] / "data"

class StartRunRequest(BaseModel):
    mode: str = "DEMO"

@router.post("/analysis-runs", status_code=201)
def start_run(request: StartRunRequest):
    run_id = str(uuid4())
    state = AnalysisRunner(DATA_ROOT).run(request.mode)
    RUNS[run_id] = state.model_dump()
    return {"run_id":run_id, "status":"COMPLETED", "mode":state.project["mode"]}

@router.get("/analysis-runs/{run_id}")
def get_run(run_id: str):
    return _get(run_id)

@router.get("/analysis-runs/{run_id}/skills/{skill_id}")
def get_skill(run_id: str, skill_id: str):
    state = _get(run_id)
    mapping = {"01":"market", "02":"market", "03":"competitors", "04":"voc", "05":"opportunities", "06":"technical_risks", "07":"lifecycle_risks", "08":"profit_analysis", "09":"decision", "10":"report"}
    return {"skill": next((item for item in state["skill_runs"] if item["skill_id"] == skill_id), None), "result":state.get(mapping.get(skill_id, ""))}

@router.get("/analysis-runs/{run_id}/evidence/{evidence_id}")
def get_evidence(run_id: str, evidence_id: str):
    state = _get(run_id)
    item = next((evidence for evidence in state["evidence"] if evidence["id"] == evidence_id), None)
    if item is None: raise HTTPException(status_code=404, detail="Evidence not found")
    return item

@router.get("/analysis-runs/{run_id}/report")
def get_report(run_id: str):
    return _get(run_id)["report"]

def _get(run_id: str) -> dict:
    if run_id not in RUNS: raise HTTPException(status_code=404, detail="Analysis run not found")
    return RUNS[run_id]

