from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.workflow.runner import AnalysisRunner
from app.services.amazon_sync import AmazonSyncService
from functools import lru_cache
from app.services.review_store import MAX_CSV_BYTES, ReviewStore

router = APIRouter(prefix="/api")
RUNS: dict[str, dict] = {}
DATA_ROOT = Path(__file__).resolve().parents[3] / "data"

def get_review_store() -> ReviewStore:
    return ReviewStore(DATA_ROOT / 'reviews_real' / 'reviews.sqlite3')

@router.post('/reviews/import', status_code=201)
async def import_reviews(request: Request, store: ReviewStore = Depends(get_review_store)):
    if request.headers.get('content-type', '').split(';')[0].strip() != 'text/csv':
        raise HTTPException(status_code=415, detail='请使用 text/csv 上传 UTF-8 文件。')
    body = await request.body()
    if len(body) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail='CSV 文件不能超过 5 MB。')
    try:
        return store.import_csv(body.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

@router.get('/reviews/stats')
def review_stats(store: ReviewStore = Depends(get_review_store)):
    return store.stats()

@lru_cache(maxsize=1)
def get_amazon_service() -> AmazonSyncService:
    return AmazonSyncService(DATA_ROOT)

@router.post('/amazon/sync')
def sync_amazon(service: AmazonSyncService = Depends(get_amazon_service)):
    return service.sync_all_competitors()

@router.get('/amazon/sync/latest')
def latest_amazon_sync(service: AmazonSyncService = Depends(get_amazon_service)):
    snapshot = service.latest_snapshot() or {'summary': {'status': 'NOT_CONFIGURED' if not service.settings.configured else 'PENDING',
        'credential_configured': service.settings.configured, 'mode': service.settings.mode},
        'products': [], 'facts': [], 'evidence': []}
    snapshot['connection_status'] = ('NOT_CONFIGURED' if not service.settings.configured else
                                     'DISABLED' if service.settings.mode == 'production' and not service.settings.real_data_enabled else
                                     'ERROR' if snapshot['summary'].get('status') == 'ERROR' else
                                     'LIVE' if service.settings.mode == 'production' and service.settings.real_data_enabled and snapshot['summary'].get('mode') == 'production' and snapshot['summary'].get('live_records', 0) else
                                     'SANDBOX' if service.settings.mode == 'sandbox' else 'FALLBACK')
    return snapshot

@router.get('/amazon/products')
def amazon_products(service: AmazonSyncService = Depends(get_amazon_service)):
    return (service.latest_snapshot() or {}).get('products', [])

@router.get('/amazon/products/{asin}')
def amazon_product(asin: str, service: AmazonSyncService = Depends(get_amazon_service)):
    products = (service.latest_snapshot() or {}).get('products', [])
    product = next((item for item in products if item['asin'] == asin), None)
    if product is None:
        raise HTTPException(status_code=404, detail='未找到该 ASIN 的同步结果。')
    return product

@router.get('/amazon/products/{asin}/feedback')
def amazon_product_feedback(asin: str, service: AmazonSyncService = Depends(get_amazon_service)):
    return amazon_product(asin, service).get('feedback', [])

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

