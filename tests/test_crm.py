from lead_qualifier.crm import CRM
from lead_qualifier.pipeline import qualify_and_log


def test_upsert_list_stats_and_export(tmp_path, icp, hot_lead, vendor_lead):
    crm = CRM(tmp_path / "crm.sqlite")
    qualify_and_log(hot_lead, icp, crm, prefer_llm=False)
    qualify_and_log(vendor_lead, icp, crm, prefer_llm=False)

    assert crm.count() == 2
    rows = crm.list_leads()
    assert {row["email"] for row in rows} == {hot_lead.email, vendor_lead.email}

    stats = crm.stats()
    assert stats["total"] == 2
    assert stats["by_tier"]["hot"] == 1
    assert stats["by_tier"]["cold"] == 1
    assert 0 < stats["average_score"] < 100

    hot_row = crm.get_by_email(hot_lead.email)
    crm.update_status(hot_row["id"], "working")
    assert crm.get(hot_row["id"])["status"] == "working"

    # Re-qualify updates rather than duplicating.
    qualify_and_log(hot_lead, icp, crm, prefer_llm=False)
    assert crm.count() == 2

    exported = crm.export_csv(tmp_path / "crm.csv")
    text = exported.read_text(encoding="utf-8")
    assert hot_lead.email in text
    assert "email_subject" in text
    crm.close()


def test_empty_stats(tmp_path):
    crm = CRM(tmp_path / "empty.sqlite")
    assert crm.stats() == {"total": 0, "average_score": 0.0, "by_tier": {"hot": 0, "warm": 0, "cold": 0}}
    crm.close()
