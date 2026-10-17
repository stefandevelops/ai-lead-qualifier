from lead_qualifier.email_draft import demo_email, draft_email
from lead_qualifier.enrich import enrich_lead
from lead_qualifier.llm import LLMConfig
from lead_qualifier.score import score_lead


def test_demo_email_uses_lead_and_is_a_draft(icp, hot_lead):
    enrichment = enrich_lead(hot_lead, icp)
    scoring = score_lead(hot_lead, enrichment, icp)
    draft = demo_email(hot_lead, enrichment, scoring, icp)
    assert draft.engine == "demo"
    assert "Maya" in draft.body
    assert "CloudLedger" in draft.subject or "CloudLedger" in draft.body
    assert "Alex Rivera" in draft.body
    assert "mailto" not in draft.body.lower()


def test_draft_email_falls_back_when_llm_fails(icp, hot_lead, monkeypatch):
    enrichment = enrich_lead(hot_lead, icp)
    scoring = score_lead(hot_lead, enrichment, icp)

    def boom(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("lead_qualifier.email_draft.generate_with_llm", boom)
    draft = draft_email(
        hot_lead,
        enrichment,
        scoring,
        icp,
        llm_config=LLMConfig(provider="openai", api_key="sk-test", model="x", base_url="http://localhost"),
    )
    assert draft.engine == "demo_fallback"
    assert "Maya" in draft.body


def test_cold_vendor_email_does_not_push_a_meeting(icp, vendor_lead):
    enrichment = enrich_lead(vendor_lead, icp)
    scoring = score_lead(vendor_lead, enrichment, icp)
    draft = demo_email(vendor_lead, enrichment, scoring, icp)
    assert "not going to push a meeting" in draft.body
