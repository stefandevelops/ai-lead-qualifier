import pytest

from lead_qualifier.icp import load_icp
from lead_qualifier.models import InboundLead


@pytest.fixture
def icp():
    return load_icp()


@pytest.fixture
def hot_lead():
    return InboundLead(
        first_name="Maya",
        last_name="Chen",
        email="maya.chen@cloudledger.io",
        title="VP Customer Success",
        company="CloudLedger",
        industry="SaaS",
        employees=420,
        country="US",
        source="demo_request",
        notes="CSMs spend Fridays rebuilding renewal forecasts from Salesforce.",
    )


@pytest.fixture
def vendor_lead():
    return InboundLead(
        first_name="Michael",
        last_name="Torres",
        email="michael.torres@salesco.io",
        title="Account Executive",
        company="SalesCo",
        industry="SaaS",
        employees=200,
        country="US",
        source="inbound_form",
        notes="Would love to show you our outbound engine.",
    )


@pytest.fixture
def intern_lead():
    return InboundLead(
        first_name="Tom",
        last_name="Bradley",
        email="tom.bradley@megabank.example",
        title="Intern",
        company="MegaBank Global",
        industry="Banking",
        employees=45000,
        country="US",
        source="careers",
        notes="Researching CS tools for a summer project.",
    )
