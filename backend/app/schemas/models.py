from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

FactStatus = Literal["CONFIRMED", "INFERRED", "UNKNOWN", "NEED_VERIFY", "CONFLICT"]
DataNature = Literal["FACT", "PUBLIC_FIXTURE", "SAMPLE", "SCENARIO", "UNKNOWN"]

class Fact(BaseModel):
    id: str
    category: str
    name: str
    value: Any = None
    unit: str | None = None
    source_type: str = "L1_INTERNAL"
    source_name: str = "PEN-X1 project brief"
    source_url: str | None = None
    source_date: str | None = None
    status: FactStatus = "CONFIRMED"
    confidence: str = "HIGH"
    data_nature: DataNature = "FACT"

class Evidence(BaseModel):
    id: str
    source: str
    content: str
    data_nature: DataNature
    status: FactStatus = "CONFIRMED"
    confidence: str = "MEDIUM"
    source_url: str | None = None

class PainPoint(BaseModel):
    pain_point: str
    aspect: str
    mentions: int
    frequency: float
    severity: str
    products: list[str]
    evidence_review_ids: list[str]
    confidence: str

class Opportunity(BaseModel):
    id: str
    title: str
    user_problem: str
    voc_evidence: list[str]
    competitor_gap: list[str]
    product_capability: str
    market_evidence: list[str]
    confidence: str
    status: FactStatus
    validation_needed: list[str] = Field(default_factory=list)

class RiskCard(BaseModel):
    risk_id: str
    stage: str
    module: str
    risk: str
    cause: str
    trigger: str
    impact: str
    severity: int = Field(ge=1, le=5)
    probability: int | None = Field(default=None, ge=1, le=5)
    detectability: int | None = Field(default=None, ge=1, le=5)
    evidence_ids: list[str] = Field(default_factory=list)
    validation_method: str
    mitigation: str
    status: FactStatus

    @property
    def risk_score(self) -> int | None:
        if self.probability is None or self.detectability is None:
            return None
        return self.severity * self.probability * self.detectability

class SkillRun(BaseModel):
    skill_id: str
    name: str
    status: Literal["PENDING", "RUNNING", "COMPLETED", "WARNING", "FAILED"] = "PENDING"
    message: str = ""

class ValidationResult(BaseModel):
    passed: bool
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

class ProfitCell(BaseModel):
    price_usd: float
    return_rate: float
    revenue_usd: float
    bom_usd: float
    amazon_fee_usd: float | None = None
    fba_usd: float | None = None
    freight_usd: float | None = None
    advertising_usd: float | None = None
    return_cost_usd: float | None = None
    contribution_margin_usd: float | None = None
    data_nature: DataNature = "SCENARIO"
