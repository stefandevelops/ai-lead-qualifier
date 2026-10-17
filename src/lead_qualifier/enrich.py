from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from lead_qualifier.icp import ICP
from lead_qualifier.models import Enrichment, InboundLead

INDUSTRY_ALIASES = {
    "saas": "SaaS",
    "software": "SaaS",
    "software as a service": "SaaS",
    "fintech": "FinTech",
    "fin tech": "FinTech",
    "financial services": "FinTech",
    "healthtech": "Healthcare IT",
    "healthcare it": "Healthcare IT",
    "health it": "Healthcare IT",
    "healthcare": "Healthcare",
    "health care": "Healthcare",
    "hr tech": "HR Tech",
    "hrtech": "HR Tech",
    "human resources": "HR Tech",
    "professional services": "Professional Services",
    "consulting": "Consulting",
    "insurance": "Insurance",
    "edtech": "EdTech",
    "education": "EdTech",
    "logistics": "Logistics",
    "freight": "Logistics",
    "agency": "Media Agency",
    "media agency": "Media Agency",
    "banking": "Banking",
    "retail": "Consumer Retail",
    "public sector": "Public Sector",
    "government": "Public Sector",
}

COUNTRY_ALIASES = {
    "USA": "US",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
    "AMERICA": "US",
    "UNITED KINGDOM": "UK",
    "GREAT BRITAIN": "UK",
    "ENGLAND": "UK",
    "GB": "UK",
    "DEUTSCHLAND": "DE",
    "GERMANY": "DE",
    "FRANCE": "FR",
    "ITALY": "IT",
    "SPAIN": "ES",
    "SWEDEN": "SE",
    "NORWAY": "NO",
    "DENMARK": "DK",
    "NETHERLANDS": "NL",
    "HOLLAND": "NL",
    "CANADA": "CA",
    "AUSTRALIA": "AU",
    "IRELAND": "IE",
    "SINGAPORE": "SG",
    "UAE": "AE",
    "UNITED ARAB EMIRATES": "AE",
    "BRAZIL": "BR",
    "SWITZERLAND": "CH",
    "AUSTRIA": "AT",
    "BELGIUM": "BE",
}

COLUMN_ALIASES = {
    "first_name": {"first_name", "firstname", "first", "given_name"},
    "last_name": {"last_name", "lastname", "last", "surname", "family_name"},
    "email": {"email", "email_address", "work_email"},
    "title": {"title", "job_title", "role", "position"},
    "company": {"company", "company_name", "account", "organization", "org"},
    "industry": {"industry", "vertical", "sector"},
    "employees": {"employees", "employee_count", "company_size", "headcount", "size"},
    "country": {"country", "country_code", "location", "geo"},
    "source": {"source", "lead_source", "inbound_source", "origin"},
    "notes": {"notes", "message", "comment", "pain", "description"},
}


def normalize_industry(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    return INDUSTRY_ALIASES.get(raw.lower(), raw)


def normalize_country(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[upper]
    if len(upper) == 2:
        return upper
    return COUNTRY_ALIASES.get(upper, upper)


def domain_from_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def parse_employees(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    digits = re.sub(r"[^\d]", "", text.split("-")[0])
    if not digits:
        return None
    return int(digits)


def _title_matches(title: str, phrases: list[str]) -> bool:
    haystack = f" {title.lower()} "
    return any(f" {phrase} " in haystack or title.lower().startswith(phrase) for phrase in phrases)


def classify_seniority(title: str, icp: ICP) -> tuple[str, str, str]:
    """Return (bucket, label, persona)."""
    if not title.strip():
        return "unknown", "Unknown", "unknown"

    lowered = title.lower()
    if _title_matches(lowered, icp.seniority.get("poor_fit", [])):
        persona = "vendor" if any(token in lowered for token in ("account executive", "sdr", "bdr", "sales development")) else "poor_fit"
        return "poor_fit", "Poor fit", persona
    if _title_matches(lowered, icp.seniority.get("economic_buyer", [])):
        return "economic_buyer", "Economic buyer", "economic_buyer"
    if _title_matches(lowered, icp.seniority.get("champion", [])):
        return "champion", "Champion", "champion"
    if _title_matches(lowered, icp.seniority.get("user", [])):
        return "user", "End user", "user"
    first_token = lowered.split()[0].rstrip(",")
    c_level = {"cto", "cmo", "cio", "coo", "cpo", "ciso", "cdo"}
    if "chief" in lowered or first_token in c_level:
        return "economic_buyer", "C-level (adjacent)", "adjacent_buyer"
    return "unknown", "Unmapped title", "unknown"


def classify_size(employees: int | None, icp: ICP) -> str:
    if employees is None:
        return "unknown"
    ideal_min = icp.company_size.get("ideal_min", 50)
    ideal_max = icp.company_size.get("ideal_max", 2000)
    ok_min = icp.company_size.get("acceptable_min", 25)
    ok_max = icp.company_size.get("acceptable_max", 5000)
    if ideal_min <= employees <= ideal_max:
        return "ideal"
    if ok_min <= employees <= ok_max:
        return "acceptable"
    if employees < ok_min:
        return "too_small"
    return "too_large"


def classify_industry(industry: str, icp: ICP) -> tuple[str, str]:
    norm = normalize_industry(industry)
    if not norm:
        return "", "unknown"
    if norm in icp.industries.get("primary", []):
        return norm, "primary"
    if norm in icp.industries.get("adjacent", []):
        return norm, "adjacent"
    if norm in icp.industries.get("poor", []):
        return norm, "poor"
    return norm, "unknown"


def classify_geo(country: str, icp: ICP) -> tuple[str, str]:
    region = normalize_country(country)
    if not region:
        return "", "unknown"
    if region in icp.geography.get("core", []):
        return region, "core"
    if region in icp.geography.get("adjacent", []):
        return region, "adjacent"
    return region, "other"


def classify_intent(lead: InboundLead, icp: ICP) -> str:
    blob = f"{lead.source} {lead.notes}".lower()
    if any(token in blob for token in icp.intent.get("low", [])):
        # High-intent words still win if the note is a real buying motion.
        if any(token in blob for token in icp.intent.get("high", [])) and "resell" not in blob:
            return "high"
        return "low"
    if any(token in blob for token in icp.intent.get("high", [])):
        return "high"
    if any(token in blob for token in icp.intent.get("medium", [])):
        return "medium"
    return "unknown"


def enrich_lead(lead: InboundLead, icp: ICP) -> Enrichment:
    seniority, seniority_label, persona = classify_seniority(lead.title, icp)
    industry_norm, industry_fit = classify_industry(lead.industry, icp)
    region, geo_fit = classify_geo(lead.country, icp)
    size_band = classify_size(lead.employees, icp)
    intent_level = classify_intent(lead, icp)

    signals: list[str] = []
    title = lead.title.lower()
    notes = (lead.notes or "").lower()
    if persona == "vendor" or any(token in title for token in ("account executive", "sdr", "bdr")):
        signals.append("vendor_outreach")
    if "intern" in title or "student" in title:
        signals.append("intern")
    if size_band == "too_small":
        signals.append("too_small")
    if size_band == "too_large":
        signals.append("too_large")
    if not lead.title or lead.employees is None:
        signals.append("incomplete")
    if "resell" in notes:
        signals.append("reseller")
    if "not looking to buy" in notes or "not sure we can buy" in notes:
        signals.append("no_budget")
    if intent_level == "high":
        signals.append("high_intent")

    return Enrichment(
        domain=domain_from_email(lead.email),
        seniority=seniority,
        seniority_label=seniority_label,
        size_band=size_band,
        region=region,
        geo_fit=geo_fit,
        industry_norm=industry_norm,
        industry_fit=industry_fit,
        persona=persona,
        intent_level=intent_level,
        signals=signals,
    )


def _mapped_columns(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for original in columns:
        key = original.strip().lower().replace(" ", "_")
        for field, aliases in COLUMN_ALIASES.items():
            if key in aliases:
                mapping[original] = field
                break
    return mapping


def _split_full_name(value: str) -> tuple[str, str]:
    parts = [part for part in str(value).strip().split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def leads_from_dataframe(frame: pd.DataFrame) -> list[InboundLead]:
    renamed = frame.rename(columns=_mapped_columns(list(frame.columns)))
    if "first_name" not in renamed.columns and "name" in {c.lower() for c in frame.columns}:
        name_col = next(c for c in frame.columns if c.lower() == "name")
        split = frame[name_col].fillna("").map(_split_full_name)
        renamed["first_name"] = [item[0] for item in split]
        renamed["last_name"] = [item[1] for item in split]

    def cell(row, key: str) -> str:
        value = row.get(key)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        text = str(value).strip()
        return "" if text.lower() in {"nan", "none", "null"} else text

    leads: list[InboundLead] = []
    for _, row in renamed.iterrows():
        email = cell(row, "email")
        if not email:
            continue
        leads.append(
            InboundLead(
                first_name=cell(row, "first_name"),
                last_name=cell(row, "last_name"),
                email=email,
                title=cell(row, "title"),
                company=cell(row, "company"),
                industry=cell(row, "industry"),
                employees=parse_employees(row.get("employees")),
                country=cell(row, "country"),
                source=cell(row, "source"),
                notes=cell(row, "notes"),
            )
        )
    return leads


def load_leads_csv(path: Path) -> list[InboundLead]:
    frame = pd.read_csv(path, keep_default_na=False)
    return leads_from_dataframe(frame)


def sample_leads_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "sample_leads.csv"


def load_sample_leads() -> list[InboundLead]:
    return load_leads_csv(sample_leads_path())
