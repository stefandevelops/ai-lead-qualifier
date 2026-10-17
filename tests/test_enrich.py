from io import StringIO

import pandas as pd

from lead_qualifier.enrich import (
    domain_from_email,
    enrich_lead,
    leads_from_dataframe,
    load_sample_leads,
    normalize_country,
    normalize_industry,
    parse_employees,
)


def test_domain_from_email():
    assert domain_from_email("maya.chen@cloudledger.io") == "cloudledger.io"
    assert domain_from_email("not-an-email") == ""


def test_parse_employees():
    assert parse_employees("1,200") == 1200
    assert parse_employees("50-200") == 50
    assert parse_employees("") is None
    assert parse_employees(420) == 420


def test_normalize_aliases():
    assert normalize_industry("fintech") == "FinTech"
    assert normalize_country("United States") == "US"
    assert normalize_country("UAE") == "AE"


def test_enrichment_for_hot_lead(icp, hot_lead):
    enrichment = enrich_lead(hot_lead, icp)
    assert enrichment.domain == "cloudledger.io"
    assert enrichment.seniority == "economic_buyer"
    assert enrichment.size_band == "ideal"
    assert enrichment.industry_fit == "primary"
    assert enrichment.geo_fit == "core"
    assert enrichment.intent_level == "high"
    assert "high_intent" in enrichment.signals


def test_vendor_and_intern_signals(icp, vendor_lead, intern_lead):
    vendor = enrich_lead(vendor_lead, icp)
    intern = enrich_lead(intern_lead, icp)
    assert "vendor_outreach" in vendor.signals
    assert vendor.seniority == "poor_fit"
    assert "intern" in intern.signals
    assert intern.size_band == "too_large"


def test_csv_aliases_and_full_name(icp):
    csv = StringIO(
        "name,email_address,job_title,company_name,headcount,location\n"
        "Priya Nair,priya@northwindhealth.com,CRO,Northwind Health,850,United States\n"
    )
    leads = leads_from_dataframe(pd.read_csv(csv))
    assert len(leads) == 1
    assert leads[0].first_name == "Priya"
    assert leads[0].last_name == "Nair"
    assert leads[0].title == "CRO"
    assert leads[0].employees == 850
    assert leads[0].country == "United States"


def test_sample_leads_are_twenty_and_fake():
    leads = load_sample_leads()
    assert len(leads) == 20
    emails = [lead.email for lead in leads]
    assert len(set(emails)) == 20
    assert all("@" in lead.email for lead in leads)
