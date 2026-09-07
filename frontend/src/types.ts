export type Skill = { skill_id: string; name: string; status: string; message: string }
export type AnalysisState = { skill_runs: Skill[]; evidence: Evidence[]; voc: { pain_points?: PainPoint[]; review_count?: number }; technical_risks: Risk[]; lifecycle_risks: Risk[]; decision: { decision: string; rationale: string[]; gates: Gate[] }; report: { markdown: string; status: string }; validation: { passed: boolean; warnings: string[]; errors: string[] }; market: Record<string, unknown>; competitors: Record<string, unknown>[]; opportunities: Record<string, unknown>[]; profit_analysis: Record<string, unknown> }
export type Evidence = { id: string; source: string; content: string; data_nature: string; status: string; confidence: string }
export type PainPoint = { pain_point: string; aspect: string; mentions: number; frequency: number; severity: string; evidence_review_ids: string[] }
export type Risk = { risk_id: string; stage: string; module: string; risk: string; severity: number; probability: number | null; status: string; validation_method: string; mitigation: string }
export type Gate = { name: string; status: string; reason: string }
