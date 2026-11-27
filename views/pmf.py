"""PMF page: where each company is on product-market fit, and the plan to get there.

Based on the Wavemaker Impact "Portfolio Acceleration" whitepaper (Nov 2024).
"""
from datetime import date

import pandas as pd
import streamlit as st

import db
import pmf_map
import styles

NUMBER_COLS = ["Metric", "Target", "Current"]
TEST_COLS = ["Hypothesis", "Test", "Owner", "Due date", "Result"]
CHECKLIST = {
    "demand_repeatable": "Demand is predictable and repeatable",
    "unit_economics_positive": "Unit economics are positive",
    "customer_group_large": "The customer group is large enough",
    "icp_defined": "Ideal customer profile (ICP) is clearly defined",
    "founder_talks_to_customers": "Founder speaks directly with customers and gets rapid feedback",
}


def nice_date(iso):
    if not iso:
        return "Not yet"
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"  # no platform-specific codes, so it works on Windows too


def to_records(df, date_cols=()):
    """Editor table -> list of dicts, dropping empty rows."""
    out = []
    for _, row in df.iterrows():
        rec = {}
        for col, val in row.items():
            if val is None or (not isinstance(val, str) and pd.isna(val)):
                val = None
            elif col in date_cols:
                val = pd.Timestamp(val).strftime("%Y-%m-%d")
            elif isinstance(val, str):
                val = val.strip() or None
            rec[col] = val
        if any(v is not None for v in rec.values()):
            out.append(rec)
    return out


def table(records, columns, date_cols=()):
    df = pd.DataFrame(records, columns=columns)
    for col in columns:
        if col in date_cols:
            df[col] = pd.to_datetime(df[col], errors="coerce")
        else:
            df[col] = df[col].astype("object").where(df[col].notna(), "")
    return df


if "pmf_flash" in st.session_state:
    st.toast(st.session_state.pop("pmf_flash"))

st.title("Product-market fit")

companies = db.list_companies()
if not companies:
    st.info("No companies yet. Add them on the Portfolio page first.")
    st.stop()

# PMF map: every assessed company placed on the startup-journey curve by its PMF stage.
mapped = [dict(c, pmf_stage=db.OLD_PMF_STAGES.get(c.get("pmf_stage"), c.get("pmf_stage"))) for c in companies]
st.plotly_chart(pmf_map.build_figure(mapped), config={"displayModeBar": False}, key="pmf_map")
unassessed = sum(1 for c in mapped if c["pmf_stage"] not in db.PMF_STAGES)
with st.container(key="pmf_map_notes"):
    if unassessed:
        styles.muted(f"{unassessed} {'company' if unassessed == 1 else 'companies'} not yet assessed")
    styles.muted("Illustrative. Position reflects each company's PMF stage, not measured valuation.")

names = {c["id"]: f"{c['name']} ({c['founder']})" if c.get("founder") else c["name"] for c in companies}
ids = list(names)
# The picker has a stable key; "pmf_company" remembers the choice when you visit another page.
if st.session_state.get("pmf_picker") not in ids:
    remembered = st.session_state.get("pmf_company")
    st.session_state["pmf_picker"] = remembered if remembered in ids else ids[0]
cid = st.selectbox("Company", ids, format_func=names.get, key="pmf_picker")
st.session_state["pmf_company"] = cid

company = db.get_company(cid)
pmf = db.get_pmf(cid)
k = f"{cid}_{st.session_state.get('pmf_ver', 0)}"  # widget keys: per company, reset after save

with st.container(key="pmf_strip"):
    s1, s2, s3, s4 = st.columns(4)
    runway = company["runway_months"]
    s1.caption("Stage")
    s1.markdown(company["stage"] or "Not set")
    s2.caption("Runway")
    s2.markdown(f"{runway:g} months" if runway is not None else "Not set")
    s3.caption("Last check-in")
    s3.markdown(nice_date(company["last_checkin"]))
    s4.caption("PMF last reviewed")
    s4.markdown(nice_date(pmf.get("last_reviewed")))

# 1. Where is this company on PMF?
with st.expander("1\\. Where is this company on PMF?", expanded=True):
    saved_stage = pmf.get("pmf_stage")
    pmf_stage = st.selectbox(
        "PMF stage", db.PMF_STAGES, key=f"stage_{k}", placeholder="Choose a stage",
        index=db.PMF_STAGES.index(saved_stage) if saved_stage in db.PMF_STAGES else None)
    target_market = st.text_input("Target market", value=pmf.get("target_market") or "",
                                  placeholder="e.g. SMEs in Southeast Asia", key=f"market_{k}")
    st.markdown("**What's true today?**")
    checks = {field: st.checkbox(label, value=bool(pmf.get(field)), key=f"{field}_{k}")
              for field, label in CHECKLIST.items()}
    evidence = st.text_area("Evidence / notes", value=pmf.get("evidence_notes") or "", key=f"evidence_{k}")

# 2. Strategic plan
with st.expander("2\\. Strategic plan (the roadmap)"):
    milestones = st.text_area("Milestones (next 12 months)", value=pmf.get("milestones") or "",
                              key=f"milestones_{k}", height=120)
    indicators = st.text_area("Success indicators", value=pmf.get("success_indicators") or "",
                              key=f"indicators_{k}")
    st.markdown("**Critical numbers**")
    numbers = st.data_editor(
        table(pmf.get("critical_numbers", []), NUMBER_COLS), key=f"numbers_{k}", num_rows="dynamic",
        hide_index=True, width="stretch",
        column_config={"Metric": st.column_config.TextColumn(width="large"),
                       "Target": st.column_config.TextColumn(),
                       "Current": st.column_config.TextColumn()})

# 3. Tactical plan
with st.expander("3\\. Tactical plan (next 1-2 quarters): minimum viable tests"):
    tests = st.data_editor(
        table(pmf.get("tests", []), TEST_COLS, date_cols=["Due date"]), key=f"tests_{k}",
        num_rows="dynamic", hide_index=True, width="stretch",
        column_config={"Hypothesis": st.column_config.TextColumn(width="large"),
                       "Test": st.column_config.TextColumn(width="large"),
                       "Owner": st.column_config.TextColumn(),
                       "Due date": st.column_config.DateColumn(format="D MMM YYYY"),
                       "Result": st.column_config.TextColumn(width="medium")})

# 4. People
with st.expander("4\\. People: founder focus"):
    f1, f2, f3 = st.columns(3, vertical_alignment="bottom")  # inputs stay level when labels wrap
    saved_focus = db.OLD_FOCUS_OPTIONS.get(pmf.get("main_focus"), pmf.get("main_focus"))
    main_focus = f1.selectbox(
        "Main focus this quarter", db.FOCUS_OPTIONS, key=f"focus_{k}", placeholder="Choose a focus",
        index=db.FOCUS_OPTIONS.index(saved_focus) if saved_focus in db.FOCUS_OPTIONS else None,
        help="Where most of the founder's working time is going this quarter.")
    conversations = f2.number_input(
        "Customer conversations in the last 30 days", min_value=0, step=1, value=pmf.get("customer_conversations"),
        key=f"conversations_{k}", placeholder="Not recorded",
        help="Number of customer interviews or calls the founder has had directly.")
    experiments = f3.number_input(
        "Experiments run this quarter", min_value=0, step=1, value=pmf.get("experiments_run"),
        key=f"experiments_{k}", placeholder="Not recorded",
        help="Number of tests the team has run this quarter to check a customer or product assumption.")
    headspace = st.text_area("How could the rest of the team give the founder headspace or help run "
                             "faster experiments?", value=pmf.get("team_headspace") or "", key=f"headspace_{k}")
    advice = st.text_area("Strategic advice the founder needs from us",
                          value=pmf.get("strategic_advice") or "", key=f"advice_{k}",
                          help="The founder's biggest ask is clarity on priorities.")

save_col, note_col = st.columns([1, 5], vertical_alignment="center")
if save_col.button("Save changes", type="primary", width="stretch"):
    db.save_pmf(cid, {
        "pmf_stage": pmf_stage,
        "target_market": target_market.strip() or None,
        **{field: int(v) for field, v in checks.items()},
        "evidence_notes": evidence.strip() or None,
        "milestones": milestones.strip() or None,
        "success_indicators": indicators.strip() or None,
        "critical_numbers": to_records(numbers),
        "tests": to_records(tests, date_cols=["Due date"]),
        "main_focus": main_focus,
        "customer_conversations": conversations,
        "experiments_run": experiments,
        "team_headspace": headspace.strip() or None,
        "strategic_advice": advice.strip() or None,
        "last_reviewed": date.today().isoformat(),
    })
    st.session_state["pmf_ver"] = st.session_state.get("pmf_ver", 0) + 1
    st.session_state["pmf_flash"] = f"Changes saved: {names[cid]}"
    st.rerun()
note_col.caption("Saving sets 'PMF last reviewed' to today. Save before switching company.")
