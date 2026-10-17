from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class InboundLead:
    first_name: str
    last_name: str
    email: str
    title: str = ""
    company: str = ""
    industry: str = ""
    employees: int | None = None
    country: str = ""
    source: str = ""
    notes: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class Enrichment:
    domain: str
    seniority: str
    seniority_label: str
    size_band: str
    region: str
    geo_fit: str
    industry_norm: str
    industry_fit: str
    persona: str
    intent_level: str
    signals: list[str] = field(default_factory=list)


@dataclass
class ScoreBreakdown:
    name: str
    points: int
    max_points: int
    note: str


@dataclass
class ScoreResult:
    score: int
    tier: str
    explanation: str
    breakdown: list[ScoreBreakdown] = field(default_factory=list)


@dataclass
class EmailDraft:
    subject: str
    body: str
    engine: str  # "demo" or "llm"


@dataclass
class Qualification:
    lead: InboundLead
    enrichment: Enrichment
    scoring: ScoreResult
    email: EmailDraft
    status: str = "outreach_drafted"

    def to_record(self) -> dict:
        record = asdict(self.lead)
        record.update(
            {
                "domain": self.enrichment.domain,
                "seniority": self.enrichment.seniority,
                "seniority_label": self.enrichment.seniority_label,
                "size_band": self.enrichment.size_band,
                "region": self.enrichment.region,
                "geo_fit": self.enrichment.geo_fit,
                "industry_norm": self.enrichment.industry_norm,
                "industry_fit": self.enrichment.industry_fit,
                "persona": self.enrichment.persona,
                "intent_level": self.enrichment.intent_level,
                "signals": "; ".join(self.enrichment.signals),
                "score": self.scoring.score,
                "tier": self.scoring.tier,
                "explanation": self.scoring.explanation,
                "email_subject": self.email.subject,
                "email_body": self.email.body,
                "draft_engine": self.email.engine,
                "status": self.status,
            }
        )
        return record
