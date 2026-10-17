from lead_qualifier.crm import CRM
from lead_qualifier.enrich import load_sample_leads
from lead_qualifier.pipeline import qualify_lead, qualify_many


def test_qualify_lead_returns_complete_record(icp, hot_lead):
    result = qualify_lead(hot_lead, icp, prefer_llm=False)
    assert result.scoring.tier == "hot"
    assert result.email.subject
    assert result.email.body
    assert result.enrichment.domain == "cloudledger.io"
    record = result.to_record()
    assert record["score"] == result.scoring.score
    assert record["email_body"] == result.email.body


def test_sample_batch_writes_twenty_rows_with_mixed_tiers(tmp_path, icp):
    crm = CRM(tmp_path / "crm.sqlite")
    results = qualify_many(load_sample_leads(), icp, crm, prefer_llm=False)
    assert len(results) == 20
    assert crm.count() == 20
    tiers = {item.scoring.tier for item in results}
    assert tiers == {"hot", "warm", "cold"}
    assert all(0 <= item.scoring.score <= 100 for item in results)
    assert all(item.email.body for item in results)
    crm.close()
