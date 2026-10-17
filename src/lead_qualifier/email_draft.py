from __future__ import annotations

from lead_qualifier.icp import ICP
from lead_qualifier.llm import LLMConfig, detect_llm, generate_with_llm
from lead_qualifier.models import EmailDraft, Enrichment, InboundLead, ScoreResult


def _first_name(lead: InboundLead) -> str:
    return lead.first_name or "there"


def _hook(lead: InboundLead) -> str:
    note = (lead.notes or "").strip()
    if note and note.lower() not in {"interested", "n/a", "na"}:
        return note if len(note) < 180 else note[:177].rsplit(" ", 1)[0] + "…"
    if lead.title and lead.company:
        return f"You are {lead.title} at {lead.company}."
    if lead.company:
        return f"You reached out from {lead.company}."
    return "You came through our inbound form."


def _product_line(icp: ICP, lead: InboundLead) -> str:
    size = f"a {lead.employees}-person team" if lead.employees else "a team your size"
    return (
        f"{icp.seller.name} is an {icp.seller.product} used by {size} "
        "to keep the next action on an account visible without another ignored dashboard."
    )


def _tidy(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(" ".join(line.split()) if line.strip() else "")
    return "\n".join(lines).strip() + "\n"


def demo_email(lead: InboundLead, enrichment: Enrichment, scoring: ScoreResult, icp: ICP) -> EmailDraft:
    name = _first_name(lead)
    company = lead.company or "your team"
    seller = icp.seller
    hook = _hook(lead)
    product = _product_line(icp, lead)
    source = lead.source.replace("_", " ") or "the website"

    if scoring.tier == "hot":
        subject = f"A cleaner weekly rhythm for {company}"
        body = f"""Hi {name},

I read your note: "{hook}"

That is the operating problem {seller.name} is built for. {product}

The inbound fit is {scoring.score} — {enrichment.seniority_label.lower()}, {enrichment.industry_norm or 'your industry'}, {enrichment.size_band.replace('_', ' ')} size — so I would keep this short.

Would a 15-minute walkthrough this week be useful, or should I send a two-page outline first?

{seller.sender_name}
{seller.sender_title}, {seller.name}
"""
    elif scoring.tier == "warm":
        subject = f"{company} and the weekly account view"
        body = f"""Hi {name},

Thanks for coming through on {source}. You wrote: "{hook}"

{product} I am not treating this as a now-or-never purchase. The score landed at {scoring.score} ({scoring.tier}), so this is a light note, not a sequence.

If it would help, I can send a one-page example of how a similar {enrichment.industry_norm or 'B2B'} team runs Monday account review.

{seller.sender_name}
{seller.sender_title}, {seller.name}
"""
    else:
        subject = f"Parking a note for {company}"
        reason = "the current fit is low"
        if "vendor_outreach" in enrichment.signals:
            reason = "this reads as vendor outbound rather than a buying request"
        elif "intern" in enrichment.signals:
            reason = "this looks like a research request"
        elif "incomplete" in enrichment.signals:
            reason = "a few required fields are still blank"
        elif enrichment.size_band == "too_small":
            reason = "the company is below the size we can support well"
        body = f"""Hi {name},

Thanks for writing in. I wanted to reply honestly: {reason}, so I am not going to push a meeting.

You mentioned: "{hook}" If that turns into a live project later, we help teams run customer operations without rebuilding the week in a spreadsheet. Happy to share a short primer if useful.

{seller.sender_name}
{seller.sender_title}, {seller.name}
"""

    return EmailDraft(subject=subject, body=_tidy(body), engine="demo")


def draft_email(
    lead: InboundLead,
    enrichment: Enrichment,
    scoring: ScoreResult,
    icp: ICP,
    llm_config: LLMConfig | None = None,
    prefer_llm: bool = True,
) -> EmailDraft:
    """Draft a first email. Uses an LLM only when a key is present and the call succeeds."""
    config = llm_config if llm_config is not None else (detect_llm() if prefer_llm else None)
    if config is not None:
        try:
            subject, body = generate_with_llm(lead, enrichment, scoring, icp, config=config)
            return EmailDraft(subject=subject, body=body, engine="llm")
        except Exception:
            fallback = demo_email(lead, enrichment, scoring, icp)
            fallback.engine = "demo_fallback"
            return fallback
    return demo_email(lead, enrichment, scoring, icp)
