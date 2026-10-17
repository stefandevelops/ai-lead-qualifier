from __future__ import annotations

from lead_qualifier.crm import CRM
from lead_qualifier.email_draft import draft_email
from lead_qualifier.enrich import enrich_lead
from lead_qualifier.icp import ICP
from lead_qualifier.llm import LLMConfig
from lead_qualifier.models import InboundLead, Qualification
from lead_qualifier.score import score_lead


def qualify_lead(
    lead: InboundLead,
    icp: ICP,
    llm_config: LLMConfig | None = None,
    prefer_llm: bool = True,
) -> Qualification:
    enrichment = enrich_lead(lead, icp)
    scoring = score_lead(lead, enrichment, icp)
    email = draft_email(
        lead,
        enrichment,
        scoring,
        icp,
        llm_config=llm_config,
        prefer_llm=prefer_llm,
    )
    return Qualification(lead=lead, enrichment=enrichment, scoring=scoring, email=email)


def qualify_and_log(
    lead: InboundLead,
    icp: ICP,
    crm: CRM,
    llm_config: LLMConfig | None = None,
    prefer_llm: bool = True,
) -> tuple[Qualification, int]:
    qualification = qualify_lead(lead, icp, llm_config=llm_config, prefer_llm=prefer_llm)
    lead_id = crm.upsert(qualification)
    return qualification, lead_id


def qualify_many(
    leads: list[InboundLead],
    icp: ICP,
    crm: CRM,
    llm_config: LLMConfig | None = None,
    prefer_llm: bool = True,
) -> list[Qualification]:
    results: list[Qualification] = []
    for lead in leads:
        qualification, _ = qualify_and_log(
            lead, icp, crm, llm_config=llm_config, prefer_llm=prefer_llm
        )
        results.append(qualification)
    return results
