from __future__ import annotations

from lead_qualifier.icp import ICP
from lead_qualifier.models import Enrichment, InboundLead, ScoreBreakdown, ScoreResult

SENIORITY_POINTS = {
    "economic_buyer": 1.0,
    "champion": 0.82,
    "user": 0.42,
    "unknown": 0.28,
    "poor_fit": 0.08,
}

SIZE_POINTS = {
    "ideal": 1.0,
    "acceptable": 0.6,
    "too_small": 0.15,
    "too_large": 0.2,
    "unknown": 0.35,
}

INDUSTRY_POINTS = {
    "primary": 1.0,
    "adjacent": 0.6,
    "unknown": 0.4,
    "poor": 0.12,
}

INTENT_POINTS = {
    "high": 1.0,
    "medium": 0.6,
    "unknown": 0.4,
    "low": 0.15,
}

GEO_POINTS = {
    "core": 1.0,
    "adjacent": 0.6,
    "unknown": 0.4,
    "other": 0.25,
}


def _pts(weight: int, ratio: float) -> int:
    return int(round(weight * ratio))


def assign_tier(score: int, icp: ICP) -> str:
    if score >= icp.hot_threshold:
        return "hot"
    if score >= icp.warm_threshold:
        return "warm"
    return "cold"


def _completeness_ratio(lead: InboundLead) -> tuple[float, str]:
    fields = [
        lead.email,
        lead.title,
        lead.company,
        lead.industry,
        lead.country,
        lead.employees is not None,
        lead.notes,
    ]
    filled = sum(1 for item in fields if item)
    ratio = filled / len(fields)
    missing = []
    if not lead.title:
        missing.append("title")
    if lead.employees is None:
        missing.append("headcount")
    if not lead.industry:
        missing.append("industry")
    if not lead.notes:
        missing.append("notes")
    note = "Complete enough to act on." if not missing else f"Missing {', '.join(missing)}."
    return ratio, note


def score_lead(lead: InboundLead, enrichment: Enrichment, icp: ICP) -> ScoreResult:
    weights = {
        "seniority": icp.weight("seniority"),
        "company_size": icp.weight("company_size"),
        "industry": icp.weight("industry"),
        "intent": icp.weight("intent"),
        "geography": icp.weight("geography"),
        "completeness": icp.weight("completeness"),
    }

    complete_ratio, complete_note = _completeness_ratio(lead)

    seniority_pts = _pts(weights["seniority"], SENIORITY_POINTS.get(enrichment.seniority, 0.28))
    size_pts = _pts(weights["company_size"], SIZE_POINTS.get(enrichment.size_band, 0.35))
    industry_pts = _pts(weights["industry"], INDUSTRY_POINTS.get(enrichment.industry_fit, 0.4))
    intent_pts = _pts(weights["intent"], INTENT_POINTS.get(enrichment.intent_level, 0.4))
    geo_pts = _pts(weights["geography"], GEO_POINTS.get(enrichment.geo_fit, 0.4))
    complete_pts = _pts(weights["completeness"], complete_ratio)

    breakdown = [
        ScoreBreakdown(
            "Seniority",
            seniority_pts,
            weights["seniority"],
            f"{lead.title or 'No title'} → {enrichment.seniority_label}.",
        ),
        ScoreBreakdown(
            "Company size",
            size_pts,
            weights["company_size"],
            f"{lead.employees if lead.employees is not None else 'Unknown'} employees → {enrichment.size_band.replace('_', ' ')}.",
        ),
        ScoreBreakdown(
            "Industry",
            industry_pts,
            weights["industry"],
            f"{enrichment.industry_norm or 'Unknown'} → {enrichment.industry_fit} fit.",
        ),
        ScoreBreakdown(
            "Intent",
            intent_pts,
            weights["intent"],
            f"Source '{lead.source or 'unspecified'}' and notes score as {enrichment.intent_level} intent.",
        ),
        ScoreBreakdown(
            "Geography",
            geo_pts,
            weights["geography"],
            f"{enrichment.region or 'Unknown'} → {enrichment.geo_fit} market.",
        ),
        ScoreBreakdown("Completeness", complete_pts, weights["completeness"], complete_note),
    ]

    score = sum(item.points for item in breakdown)
    cap_notes: list[str] = []

    if "intern" in enrichment.signals:
        score = min(score, 35)
        cap_notes.append("Capped at 35 because this is an intern or student research request.")
    if "vendor_outreach" in enrichment.signals:
        score = min(score, 42)
        cap_notes.append("Capped at 42 — this looks like vendor outreach (someone selling to us, not buying).")
    if "reseller" in enrichment.signals:
        score = min(score, 48)
        cap_notes.append("Capped at 48 — they want to resell the product, not run it.")
    if enrichment.size_band == "too_small" and (lead.employees or 0) < 10:
        score = min(score, 52)
        cap_notes.append("Capped at 52 — the company is below a workable buying floor.")
    if "incomplete" in enrichment.signals and not lead.title:
        score = min(score, 45)
        cap_notes.append("Capped at 45 — too many required fields are blank to treat this as a real opportunity.")

    score = max(0, min(100, score))
    tier = assign_tier(score, icp)

    lines = [
        f"Score {score} ({tier.title()}).",
        "",
        "Why this number:",
    ]
    for item in breakdown:
        lines.append(f"- {item.name}: {item.points}/{item.max_points}. {item.note}")
    if cap_notes:
        lines.append("")
        lines.append("Guardrails:")
        lines.extend(f"- {note}" for note in cap_notes)

    next_step = {
        "hot": "Worth a same-day personal note from an AE.",
        "warm": "Worth a short, specific email. Do not put it at the front of the queue.",
        "cold": "Keep the draft on file. I would not spend live selling time here.",
    }[tier]
    lines.extend(["", f"Suggested motion: {next_step}"])

    return ScoreResult(score=score, tier=tier, explanation="\n".join(lines), breakdown=breakdown)
