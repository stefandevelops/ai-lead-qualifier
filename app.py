from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from lead_qualifier.crm import CRM
from lead_qualifier.enrich import leads_from_dataframe, load_sample_leads
from lead_qualifier.icp import DEFAULT_ICP_PATH, dump_icp, load_icp
from lead_qualifier.llm import detect_llm
from lead_qualifier.models import InboundLead
from lead_qualifier.pipeline import qualify_and_log, qualify_many

TIER_COLORS = {
    "hot": ("#c45c26", "#fde8dc"),
    "warm": ("#8a6d1b", "#f3e6b3"),
    "cold": ("#5b6b7a", "#e4e8ec"),
}


def _db_path() -> Path:
    return Path(os.environ.get("LEAD_QUALIFIER_DB", ROOT / "data" / "crm.sqlite"))


@st.cache_resource
def get_crm() -> CRM:
    return CRM(_db_path())


def _engine_label() -> tuple[str, bool]:
    cfg = detect_llm()
    if cfg:
        return f"LLM drafts on ({cfg.provider} / {cfg.model})", True
    return "Demo drafts on — no API key needed", False


def _seed_if_empty(crm: CRM, icp) -> None:
    if crm.count() == 0:
        qualify_many(load_sample_leads(), icp, crm, prefer_llm=False)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.4rem; max-width: 1180px; }
        .hero-kicker { font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; color: #5b6b7a; margin-bottom: 0.2rem; }
        .hero-title { font-size: 1.85rem; font-weight: 650; line-height: 1.2; margin: 0 0 0.35rem 0; }
        .hero-sub { color: #3d4a57; margin-bottom: 0.8rem; }
        .draft-banner { background: #efe8dc; border: 1px solid #d9cbb3; padding: 0.55rem 0.8rem; border-radius: 8px; font-size: 0.92rem; }
        .lead-card { border-radius: 10px; padding: 0.75rem 0.85rem; margin-bottom: 0.65rem; border: 1px solid #e0d6c6; }
        .lead-card h4 { margin: 0 0 0.15rem 0; font-size: 0.98rem; }
        .lead-card p { margin: 0.15rem 0; font-size: 0.86rem; color: #3d4a57; }
        .score-pill { display: inline-block; font-weight: 650; font-size: 0.82rem; }
        .muted { color: #5b6b7a; font-size: 0.86rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _tier_badge(tier: str, score: int) -> str:
    color, _ = TIER_COLORS.get(tier, TIER_COLORS["cold"])
    return f'<span class="score-pill" style="color:{color}">{tier.upper()} · {score}</span>'


def render_header() -> None:
    engine, live = _engine_label()
    st.markdown(
        """
        <div class="hero-kicker">Northstar CS · portfolio demo</div>
        <div class="hero-title">AI lead qualifier</div>
        <p class="hero-sub">Inbound lead in. Score, tier, and a first email draft out. Logged to a local CRM. Nothing is sent.</p>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns([3, 2])
    with cols[0]:
        st.markdown(f'<div class="draft-banner"><strong>Drafts only.</strong> {engine}.</div>', unsafe_allow_html=True)
    with cols[1]:
        st.caption("Optional live drafts: set OPENAI_API_KEY or GEMINI_API_KEY. The app stays usable without them.")
        if live:
            st.success("An API key is set for this session.")


def page_dashboard(crm: CRM) -> None:
    stats = crm.stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads in CRM", stats["total"])
    c2.metric("Average score", stats["average_score"])
    c3.metric("Hot", stats["by_tier"].get("hot", 0))
    c4.metric("Warm / cold", f"{stats['by_tier'].get('warm', 0)} / {stats['by_tier'].get('cold', 0)}")

    rows = crm.list_leads()
    if not rows:
        st.info("No leads yet. Open Ingest and load the sample list or submit the form.")
        return

    chart = pd.DataFrame(
        {
            "Tier": ["Hot", "Warm", "Cold"],
            "Leads": [
                stats["by_tier"].get("hot", 0),
                stats["by_tier"].get("warm", 0),
                stats["by_tier"].get("cold", 0),
            ],
        }
    )
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Leads by tier")
        st.bar_chart(chart.set_index("Tier"))
    with right:
        st.subheader("Highest-scoring leads")
        preview = pd.DataFrame(rows)[
            ["first_name", "last_name", "company", "title", "score", "tier", "intent_level"]
        ].head(8)
        preview.columns = ["First", "Last", "Company", "Title", "Score", "Tier", "Intent"]
        st.dataframe(preview, hide_index=True, use_container_width=True)

    st.subheader("What the scores are saying")
    for row in rows[:3]:
        with st.expander(f"{row['first_name']} {row['last_name']} · {row['company']} · {row['score']} ({row['tier']})"):
            st.text(row["explanation"])
            st.markdown("**Draft subject**")
            st.write(row["email_subject"])
            st.markdown("**Draft body**")
            st.text(row["email_body"])


def _show_qualification(result) -> None:
    color, bg = TIER_COLORS[result.scoring.tier]
    st.markdown(
        f"""
        <div class="lead-card" style="background:{bg}; border-left: 4px solid {color};">
          <h4>{result.lead.full_name} · {result.lead.company or 'No company'}</h4>
          <p>{_tier_badge(result.scoring.tier, result.scoring.score)}</p>
          <p>{result.lead.title} · {result.enrichment.industry_norm or result.lead.industry or 'Industry unknown'} · {result.enrichment.domain}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    tabs = st.tabs(["Why this score", "Email draft", "Enrichment"])
    with tabs[0]:
        st.text(result.scoring.explanation)
    with tabs[1]:
        st.caption(f"Engine: {result.email.engine} · drafts are never sent")
        st.markdown(f"**Subject:** {result.email.subject}")
        st.text(result.email.body)
    with tabs[2]:
        st.write(
            {
                "domain": result.enrichment.domain,
                "seniority": result.enrichment.seniority_label,
                "persona": result.enrichment.persona,
                "size_band": result.enrichment.size_band,
                "industry": f"{result.enrichment.industry_norm} ({result.enrichment.industry_fit})",
                "region": f"{result.enrichment.region} ({result.enrichment.geo_fit})",
                "intent": result.enrichment.intent_level,
                "signals": result.enrichment.signals,
            }
        )


def page_ingest(crm: CRM, icp) -> None:
    st.subheader("Bring a lead in")
    st.caption("Use the 20 fake sample leads, upload a CSV, or type one by hand. Re-submitting the same email updates the CRM row.")

    sample_tab, csv_tab, form_tab = st.tabs(["Sample leads", "CSV upload", "Web form"])

    with sample_tab:
        st.write("20 realistic fake inbound leads for a fictional B2B seller, Northstar CS. Mix of hot, warm, and cold.")
        if st.button("Load / refresh the 20 sample leads", type="primary"):
            results = qualify_many(load_sample_leads(), icp, crm, prefer_llm=bool(detect_llm()))
            st.success(f"Qualified {len(results)} sample leads and wrote them to the CRM.")
            st.session_state["last_result"] = results[0]

    with csv_tab:
        uploaded = st.file_uploader("CSV with inbound leads", type=["csv"])
        st.caption("Columns: first_name, last_name, email, title, company, industry, employees, country, source, notes. Name aliases are accepted.")
        if uploaded is not None:
            frame = pd.read_csv(uploaded)
            st.dataframe(frame.head(12), use_container_width=True, hide_index=True)
            if st.button("Qualify uploaded leads", type="primary"):
                leads = leads_from_dataframe(frame)
                if not leads:
                    st.error("No rows with an email address were found.")
                else:
                    results = qualify_many(leads, icp, crm, prefer_llm=bool(detect_llm()))
                    st.success(f"Qualified {len(results)} leads.")
                    st.session_state["last_result"] = results[0]

    with form_tab:
        with st.form("inbound_form"):
            c1, c2 = st.columns(2)
            first_name = c1.text_input("First name", placeholder="Maya")
            last_name = c2.text_input("Last name", placeholder="Chen")
            email = st.text_input("Work email", placeholder="maya.chen@cloudledger.io")
            c3, c4 = st.columns(2)
            title = c3.text_input("Title", placeholder="VP Customer Success")
            company = c4.text_input("Company", placeholder="CloudLedger")
            c5, c6, c7 = st.columns(3)
            industry = c5.text_input("Industry", placeholder="SaaS")
            employees = c6.number_input("Employees", min_value=0, value=0, step=10)
            country = c7.text_input("Country", placeholder="US")
            source = st.selectbox(
                "How they arrived",
                ["demo_request", "pricing", "trial", "webinar", "content_download", "inbound_form", "partner_referral", "newsletter", "website_form"],
            )
            notes = st.text_area("What they said", placeholder="CSMs are rebuilding renewal forecasts from three spreadsheets.")
            submitted = st.form_submit_button("Qualify this lead", type="primary")
        if submitted:
            if not email.strip():
                st.error("Email is required.")
            else:
                lead = InboundLead(
                    first_name=first_name.strip(),
                    last_name=last_name.strip(),
                    email=email.strip(),
                    title=title.strip(),
                    company=company.strip(),
                    industry=industry.strip(),
                    employees=int(employees) if employees else None,
                    country=country.strip(),
                    source=source,
                    notes=notes.strip(),
                )
                result, _ = qualify_and_log(lead, icp, crm, prefer_llm=bool(detect_llm()))
                st.session_state["last_result"] = result
                st.success("Scored, drafted, and written to the CRM.")

    if "last_result" in st.session_state:
        st.divider()
        st.subheader("Latest qualification")
        _show_qualification(st.session_state["last_result"])


def page_pipeline(crm: CRM) -> None:
    st.subheader("Pipeline by tier")
    st.caption("Same CRM rows, grouped the way a sales manager actually triages an inbound list.")
    cols = st.columns(3)
    for column, tier in zip(cols, ("hot", "warm", "cold")):
        color, bg = TIER_COLORS[tier]
        leads = crm.list_leads(tier)
        with column:
            st.markdown(
                f"<h3 style='color:{color}; margin-bottom:0.2rem'>{tier.title()} <span class='muted'>({len(leads)})</span></h3>",
                unsafe_allow_html=True,
            )
            if not leads:
                st.caption("None yet.")
            for row in leads:
                st.markdown(
                    f"""
                    <div class="lead-card" style="background:{bg};">
                      <h4>{row['first_name']} {row['last_name']}</h4>
                      <p>{row['title'] or 'No title'} · {row['company'] or 'No company'}</p>
                      <p>{_tier_badge(row['tier'], row['score'])} · {row['intent_level']} intent</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander("Open"):
                    st.text(row["explanation"])
                    st.markdown(f"**{row['email_subject']}**")
                    st.text(row["email_body"])
                    new_status = st.selectbox(
                        "CRM status",
                        ["outreach_drafted", "in_review", "working", "archived"],
                        index=["outreach_drafted", "in_review", "working", "archived"].index(row["status"])
                        if row["status"] in {"outreach_drafted", "in_review", "working", "archived"}
                        else 0,
                        key=f"status-{row['id']}",
                    )
                    if new_status != row["status"]:
                        crm.update_status(row["id"], new_status)
                        st.rerun()


def page_crm(crm: CRM) -> None:
    st.subheader("Local CRM")
    st.caption("SQLite on disk. Export is a plain CSV you can open in Sheets or HubSpot's importer.")
    rows = crm.list_leads()
    if not rows:
        st.info("CRM is empty.")
        return
    frame = pd.DataFrame(rows)
    visible = frame[
        [
            "id",
            "first_name",
            "last_name",
            "email",
            "company",
            "title",
            "score",
            "tier",
            "status",
            "email_subject",
            "updated_at",
        ]
    ]
    st.dataframe(visible, use_container_width=True, hide_index=True)
    st.download_button(
        "Export CRM as CSV",
        data=crm.export_csv_text(),
        file_name="lead_qualifier_crm.csv",
        mime="text/csv",
    )
    picked = st.selectbox(
        "Inspect a row",
        options=frame["id"].tolist(),
        format_func=lambda i: f"#{i} · {frame.loc[frame['id']==i, 'first_name'].iloc[0]} {frame.loc[frame['id']==i, 'last_name'].iloc[0]} · {frame.loc[frame['id']==i, 'company'].iloc[0]}",
    )
    row = crm.get(int(picked))
    if row:
        st.text(row["explanation"])
        st.markdown(f"**{row['email_subject']}**")
        st.text(row["email_body"])


def page_icp(icp) -> None:
    st.subheader("Ideal customer profile")
    st.caption("Scoring is deterministic and readable. This page is the contract a sales manager can argue with.")
    seller = icp.seller
    st.markdown(f"**Seller:** {seller.name} · {seller.product}")
    st.markdown(f"**From:** {seller.sender_name}, {seller.sender_title} · {seller.sender_email}")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Weights (must add up to 100)**")
        st.table(pd.DataFrame({"Dimension": list(icp.weights.keys()), "Weight": list(icp.weights.values())}))
        st.markdown(f"**Tiers:** hot ≥ {icp.hot_threshold}, warm ≥ {icp.warm_threshold}, else cold")
    with c2:
        st.markdown("**Company size**")
        st.json(icp.company_size)
        st.markdown("**Industries**")
        st.json(icp.industries)

    st.markdown("**Geography and intent keywords**")
    g1, g2 = st.columns(2)
    g1.json(icp.geography)
    g2.json(icp.intent)
    st.caption(f"Loaded from `{DEFAULT_ICP_PATH.name}`. Change the YAML and restart the app to rescore after reloading samples.")
    with st.expander("Raw ICP as the scorer sees it"):
        st.json(dump_icp(icp))


def main() -> None:
    st.set_page_config(page_title="AI Lead Qualifier", page_icon="◎", layout="wide")
    _inject_css()
    icp = load_icp()
    crm = get_crm()
    _seed_if_empty(crm, icp)

    render_header()
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Ingest", "Pipeline", "CRM", "ICP"],
        index=0,
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("**How to read this demo**")
    st.sidebar.caption(
        "Dashboard is the 30-second view. Ingest is the product. Pipeline is how a manager would work the list. CRM is the system of record. ICP is the scoring contract."
    )

    if page == "Dashboard":
        page_dashboard(crm)
    elif page == "Ingest":
        page_ingest(crm, icp)
    elif page == "Pipeline":
        page_pipeline(crm)
    elif page == "CRM":
        page_crm(crm)
    else:
        page_icp(icp)


if __name__ == "__main__":
    main()
