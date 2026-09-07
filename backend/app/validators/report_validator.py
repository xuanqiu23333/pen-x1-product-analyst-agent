import re
from app.schemas.models import Claim, ValidationResult
from app.schemas.state import AnalysisState

def validate_claims(state: AnalysisState, claims: list[Claim]) -> ValidationResult:
    fact_ids={fact.id for fact in state.facts}; evidence_ids={item.id for item in state.evidence}; errors=[]; warnings=[]
    for claim in claims:
        facts_ok=not claim.fact_ids or all(item in fact_ids for item in claim.fact_ids)
        evidence_ok=not claim.evidence_ids or all(item in evidence_ids for item in claim.evidence_ids)
        if claim.status=='UNSUPPORTED' or not facts_ok or not evidence_ok: errors.append(f'声明不可支持：{claim.text}')
        elif claim.status in {'INFERRED','NEED_VERIFY','CONFLICT'}: warnings.append(f'声明需谨慎表达：{claim.text}')
    return ValidationResult(passed=not errors,warnings=warnings,errors=errors)

def extract_claims(state: AnalysisState) -> list[Claim]:
    claims=[]
    if state.fact_by_id('battery_configurations'):
        claims.append(Claim(claim_id='claim-battery-configurations',text='PEN-X1 支持五种电池配置',claim_type='product_fact',fact_ids=['battery_configurations'],status='SUPPORTED'))
    text=state.report.get('markdown','')
    for index, match in enumerate(re.finditer(r'\b\d+\s*(?:流明|lumen|小时|hour|IP\d+)',text,re.I),1):
        claims.append(Claim(claim_id=f'claim-numeric-{index}',text=match.group(0),claim_type='numeric',status='UNSUPPORTED'))
    return claims

def validate_report(state: AnalysisState) -> ValidationResult:
    claims=state.report.get('claims') or extract_claims(state)
    parsed=[item if isinstance(item,Claim) else Claim.model_validate(item) for item in claims]
    state.report['claims']=[item.model_dump() for item in parsed]
    return validate_claims(state,parsed)
