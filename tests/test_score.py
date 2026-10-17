from lead_qualifier.enrich import enrich_lead
from lead_qualifier.models import InboundLead
from lead_qualifier.score import assign_tier, score_lead


def _score(lead, icp):
    return score_lead(lead, enrich_lead(lead, icp), icp)


def test_hot_lead_is_hot(icp, hot_lead):
    result = _score(hot_lead, icp)
    assert result.score >= 85
    assert result.tier == "hot"
    assert "Why this number" in result.explanation
    assert result.score <= 100


def test_vendor_is_capped_cold(icp, vendor_lead):
    result = _score(vendor_lead, icp)
    assert result.score <= 42
    assert result.tier == "cold"
    assert "vendor" in result.explanation.lower()


def test_intern_is_capped_cold(icp, intern_lead):
    result = _score(intern_lead, icp)
    assert result.score <= 35
    assert result.tier == "cold"


def test_incomplete_lead_is_capped(icp):
    lead = InboundLead(
        first_name="John",
        last_name="Harper",
        email="john.harper@acmesupplies.example",
        company="Acme Supplies",
        country="US",
        source="website_form",
        notes="Interested",
    )
    result = _score(lead, icp)
    assert result.score <= 45
    assert result.tier == "cold"


def test_tier_thresholds(icp):
    assert assign_tier(90, icp) == "hot"
    assert assign_tier(60, icp) == "warm"
    assert assign_tier(20, icp) == "cold"


def test_breakdown_adds_to_score_unless_capped(icp, hot_lead):
    enrichment = enrich_lead(hot_lead, icp)
    result = score_lead(hot_lead, enrichment, icp)
    raw = sum(item.points for item in result.breakdown)
    assert result.score == min(raw, 100)
    assert {item.name for item in result.breakdown} == {
        "Seniority",
        "Company size",
        "Industry",
        "Intent",
        "Geography",
        "Completeness",
    }
