from app.schemas.models import ValidationResult
from app.schemas.state import AnalysisState

UNSUPPORTED_TERMS = ["1000 lumens", "500 lumens", "IP68", "10-hour runtime"]

def validate_report(state: AnalysisState) -> ValidationResult:
    text = state.report.get("markdown", "").lower()
    errors = [f"Unsupported claim: {term}" for term in UNSUPPORTED_TERMS if term in text]
    warnings = []
    if not state.opportunities or not all(item.get("voc_evidence") and item.get("competitor_gap") for item in state.opportunities): warnings.append("An opportunity lacks complete supporting evidence.")
    if not all(risk.get("validation_method") and risk.get("mitigation") for risk in state.technical_risks + state.lifecycle_risks): errors.append("A risk lacks validation or mitigation.")
    return ValidationResult(passed=not errors, warnings=warnings, errors=errors)
