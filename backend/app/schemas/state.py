from __future__ import annotations
from pydantic import BaseModel, Field
from .models import Evidence, Fact, SkillRun, ValidationResult

class AnalysisState(BaseModel):
    project: dict = Field(default_factory=dict)
    facts: list[Fact] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    market: dict = Field(default_factory=dict)
    competitors: list[dict] = Field(default_factory=list)
    voc: dict = Field(default_factory=dict)
    opportunities: list[dict] = Field(default_factory=list)
    technical_risks: list[dict] = Field(default_factory=list)
    lifecycle_risks: list[dict] = Field(default_factory=list)
    profit_analysis: dict = Field(default_factory=dict)
    swot: dict = Field(default_factory=dict)
    decision: dict = Field(default_factory=dict)
    report: dict = Field(default_factory=dict)
    validation: ValidationResult | None = None
    skill_runs: list[SkillRun] = Field(default_factory=list)

    def fact_by_id(self, fact_id: str) -> Fact | None:
        return next((fact for fact in self.facts if fact.id == fact_id), None)

    def add_evidence(self, item: Evidence) -> None:
        if not any(existing.id == item.id for existing in self.evidence):
            self.evidence.append(item)
