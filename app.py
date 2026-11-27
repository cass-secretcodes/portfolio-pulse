"""Portfolio dashboard. Run with:  streamlit run app.py

This file is the Portfolio page and sets up navigation. The PMF page lives in views/pmf.py.
(Not a "pages/" folder: Streamlit would auto-load that and show the wrong navigation after a restart.)
All visual styling lives in styles.py and .streamlit/config.toml.
"""
from datetime import date

import pandas as pd
import streamlit as st

import csv_io
import db
import styles

st.set_page_config(page_title="Investible", layout="wide", initial_sidebar_state="collapsed")
styles.apply()

LABELS = db.COMPANY_FIELDS          # db column -> display label (includes Status)
TEXT_FIELDS = ["name", "status", "founder", "stage", "last_fundraise", "industry", "sector", "country", "raise",
               "notes"]

# The on-screen table adds read-only columns: PMF, Founder's focus, Runway flag and Since check-in.
TABLE_ORDER = ["Company name", "Status", "Founder", "Stage", "PMF", "Founder's focus", "Last fundraise",
               "Runway (months)", "Runway flag", "Industry", "Sector", "Country", "Last check-in", "Since check-in",
               "Raise", "Notes"]
READ_ONLY = ["PMF", "Founder's focus", "Runway flag", "Since check-in"]
SORTS = ["Company name (A-Z)", "Status (red first)", "Days since check-in (longest first)"]
ROW_HEIGHT = 40


# ---------------------------------------------------------------- helpers

def bump():
    """Reset table editors after a write so they reload from the database."""
    st.session_state["ver"] = st.session_state.get("ver", 0) + 1


def flash(message):
    st.session_state["flash"] = message


def plural(n, word="company", many="companies"):
    return f"{n} {word if n == 1 else many}"


def clean(value):
    """Normalise a cell value for saving/comparing: blanks -> None, dates -> ISO text."""
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, date)):
        return None if pd.isna(value) else value.strftime("%Y-%m-%d")
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def status_value(value):
    """The Status pill cell holds a list; a company has one status, so use the latest one picked."""
    if isinstance(value, (list, tuple)):
        return value[-1] if len(value) else None
    return clean(value)


def companies_frame(companies):
    df = pd.DataFrame(companies, columns=["id"] + list(LABELS)).set_index("id")
    df["runway_months"] = pd.to_numeric(df["runway_months"], errors="coerce")
    df["last_checkin"] = pd.to_datetime(df["last_checkin"], errors="coerce").dt.date
    df[TEXT_FIELDS] = df[TEXT_FIELDS].fillna("")
    return df.rename(columns=LABELS)


def days_since(companies_df):
    checkin = pd.to_datetime(companies_df["Last check-in"], errors="coerce")
    days = (pd.Timestamp(date.today()) - checkin).dt.days
    return days.where(days >= 0).astype("Int64")  # a future date counts as blank


def table_frame(companies):
    """Companies with the extra columns used for filtering and sorting (Days since check-in is numeric)."""
    df = companies_frame(companies)
    extra = pd.DataFrame(companies).set_index("id")
    df["PMF"] = extra["pmf_stage"].map(lambda s: db.OLD_PMF_STAGES.get(s, s)).fillna("")
    df["Founder's focus"] = extra["main_focus"].fillna("")
    df["Runway flag"] = df["Runway (months)"].map(runway_flag)
    df["Days since check-in"] = days_since(df)
    return df


def display_frame(df):
    """Turn the working frame into what the table shows: Status as a pill, check-in as '12 days ago'."""
    out = df.copy()
    out["Status"] = out["Status"].map(lambda s: [s] if s else [])
    out["Since check-in"] = [NO_CHECKIN if pd.isna(when) else relative_days(days)
                             for when, days in zip(out["Last check-in"], out["Days since check-in"])]
    return out[TABLE_ORDER]


NO_CHECKIN = "No check-in yet"


def relative_days(days):
    if pd.isna(days):
        return ""
    days = int(days)  # can arrive as 72.0 when some companies have no check-in date
    return "Today" if days == 0 else "1 day ago" if days == 1 else f"{days} days ago"


def sort_table(df, how):
    if how == "Status (red first)":
        rank = df["Status"].map({"Red": 0, "Amber": 1, "Green": 2}).fillna(3)
        return df.assign(_rank=rank).sort_values(["_rank", "Company name"]).drop(columns="_rank")
    if how == "Days since check-in (longest first)":
        return df.sort_values(["Days since check-in", "Company name"], ascending=[False, True],
                              na_position="last")
    return df.sort_values("Company name", key=lambda s: s.str.lower())


def runway_flag(months):
    if pd.isna(months):
        return ""
    return "Under 6" if months < 6 else "6-12" if months <= 12 else ""


def flag_colour(flag):
    return styles.CELL_RED if flag == "Under 6" else styles.CELL_AMBER if flag == "6-12" else ""


def days_colour(days):
    if pd.isna(days):
        return ""
    return styles.CELL_RED if days > 60 else styles.CELL_AMBER if days > 45 else ""


def row_values(row):
    values = {field: clean(row[label]) for field, label in LABELS.items()}
    values["status"] = status_value(row["Status"])
    return values


def picker_label(company):
    """Name plus founder, so two similar names can be told apart in drop-downs."""
    return f"{company['name']} ({company['founder']})" if company.get("founder") else company["name"]


def duplicate_names(companies, new_names):
    """Names in new_names {id: name} that clash with another company (case-insensitive)."""
    final = {c["id"]: c["name"] for c in companies}
    final.update(new_names)
    seen = {}
    for cid, name in final.items():
        seen.setdefault((name or "").strip().lower(), []).append(cid)
    return sorted({new_names[cid] for cid in new_names
                   if new_names[cid] and len(seen[new_names[cid].strip().lower()]) > 1})


def summary(df):
    raise_text = df["Raise"].fillna("").str.strip().str.lower()
    return [
        ("Companies", len(df)),
        ("Raising now", int(((raise_text != "") & (raise_text != "not raising")).sum())),
        ("Runway under 6 months", int((df["Runway (months)"] < 6).sum())),
        ("No check-in in 45+ days", int((df["Days since check-in"] > 45).sum())),
    ]


# ---------------------------------------------------------------- dialogs

@st.dialog("Add company", width="large")
def add_company_dialog():
    existing = {c["name"].strip().lower() for c in db.list_companies()}
    with st.form("add_company", border=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Company name *")
        founder = c2.text_input("Founder")
        status = c1.selectbox("Status", db.STATUSES, index=None, placeholder="Choose a status")
        stage = c2.selectbox("Stage", db.STAGES, index=None, placeholder="Choose a stage")
        industry = c1.selectbox("Industry", db.INDUSTRIES, index=None, placeholder="Choose an industry")
        sector = c2.text_input("Sector", placeholder="Sub-sector, e.g. carbon accounting")
        country = c1.selectbox("Country", db.COUNTRIES, index=None, placeholder="Choose a country")
        last_fundraise = c2.text_input("Last fundraise", placeholder="e.g. Seed, US$1.5M, Mar 2025")
        runway = c1.number_input("Runway (months)", min_value=0.0, step=0.5, value=None)
        last_checkin = c2.date_input("Last check-in", value=None, format="DD/MM/YYYY", max_value=date.today())
        raise_text = c1.text_input("Raise", placeholder="Current or planned raise")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add company", type="primary")

    if submitted:
        if not name.strip():
            st.error("Company name is required.")
        elif name.strip().lower() in existing:
            st.error(f"There is already a company called {name.strip()}.")
        else:
            db.add_company({
                "name": name.strip(), "status": status, "founder": clean(founder), "stage": stage,
                "last_fundraise": clean(last_fundraise), "runway_months": runway, "industry": industry,
                "sector": clean(sector), "country": country, "last_checkin": clean(last_checkin),
                "raise": clean(raise_text),
                "notes": clean(notes),
            })
            flash(f"Company added: {name.strip()}")
            bump()
            st.rerun()


@st.dialog("Import CSV", width="large")
def import_dialog():
    st.caption("Match the template's column headers; only Company name is required. A company that already "
               "exists is updated, and blank cells never overwrite saved values, so importing a file twice is "
               "safe. Dates as YYYY-MM-DD or DD/MM/YYYY.")
    st.download_button("Download CSV template", csv_io.template_bytes(), "portfolio_template.csv", "text/csv")
    upload = st.file_uploader("CSV file", type="csv", key=f"csv_{st.session_state.get('ver', 0)}")
    if upload is None:
        return
    records, problems = csv_io.parse(upload)
    if problems:
        st.warning("**Some values were skipped:**\n" + "\n".join(f"- {p}" for p in problems))
    if not records:
        return
    table = csv_io.preview(records)
    st.dataframe(table, hide_index=True, width="stretch")
    adds = int((table["Action"] == "Add").sum())
    st.caption(f"{adds} to add, {len(table) - adds} to update.")
    if st.button(f"Import {plural(len(records))}", type="primary"):
        counts = csv_io.apply(records)
        flash(f"CSV imported: {counts['added']} added, {counts['updated']} updated, "
              f"{plural(counts['tests_added'], 'test', 'tests')} added to tactical plans")
        bump()
        st.rerun()


# ---------------------------------------------------------------- page

def portfolio_page():
    if "flash" in st.session_state:
        st.toast(st.session_state.pop("flash"))

    companies = db.list_companies()

    title, actions = st.columns([1, 2], vertical_alignment="center")
    with title:
        st.title("Portfolio")
        styles.muted(plural(len(companies)))
    with actions:
        with st.container(horizontal=True, horizontal_alignment="right", key="header_actions"):
            if st.button("Import CSV", key="hdr_import"):
                import_dialog()
            st.download_button("Export CSV", csv_io.export_bytes(companies) if companies else csv_io.template_bytes(),
                               f"portfolio_{date.today().isoformat()}.csv", "text/csv", disabled=not companies)
            if st.button("Add company", type="primary", key="hdr_add"):
                add_company_dialog()

    if not companies:
        empty_state()
        return

    df = table_frame(companies)
    styles.stat_tiles(summary(df))

    f1, f2, f3, f4, f5 = st.columns([2, 1, 1, 1, 1])
    search = f1.text_input("Search", placeholder="Company or founder name")
    stages = f2.multiselect("Stage", db.STAGES, placeholder="All stages")
    industries = f3.multiselect("Industry", db.INDUSTRIES, placeholder="All industries")
    countries = f4.multiselect("Country", db.COUNTRIES, placeholder="All countries")
    sort = f5.selectbox("Sort by", SORTS)

    view = df
    if search.strip():
        q = search.strip().lower()
        view = view[view["Company name"].fillna("").str.lower().str.contains(q, regex=False)
                    | view["Founder"].fillna("").str.lower().str.contains(q, regex=False)]
    if stages:
        view = view[view["Stage"].isin(stages)]
    if industries:
        view = view[view["Industry"].isin(industries)]
    if countries:
        view = view[view["Country"].isin(countries)]
    view = sort_table(view, sort)

    shown = len(view)
    if shown != len(df):
        st.caption(f"Showing {shown} of {plural(len(df))}")

    days = view["Days since check-in"]
    shown_df = display_frame(view)
    styled = (shown_df.style
              .apply(lambda col: [f"color: {styles.MUTED}" if text == NO_CHECKIN else days_colour(d)
                                  for text, d in zip(col, days)], subset=["Since check-in"])
              .map(flag_colour, subset=["Runway flag"]))

    editor_key = f"portfolio_{st.session_state.get('ver', 0)}_{search}_{stages}_{industries}_{countries}_{sort}"
    edited = st.data_editor(
        styled,
        key=editor_key,
        hide_index=True,
        disabled=READ_ONLY,
        num_rows="fixed",
        width="stretch",
        row_height=ROW_HEIGHT,
        height=min(ROW_HEIGHT * (shown + 1) + 3, ROW_HEIGHT * 16 + 3),
        column_config={
            "Company name": st.column_config.TextColumn(required=True, pinned=True),
            "Status": st.column_config.MultiselectColumn(
                options=db.STATUSES, color=[styles.STATUS_PILL_COLOURS[s] for s in db.STATUSES],
                help="Green, Amber or Red. If you pick more than one, the last one picked is saved."),
            "PMF": st.column_config.TextColumn(width="medium", help="PMF stage saved on the PMF page (read-only)"),
            "Founder's focus": st.column_config.TextColumn(
                width="medium", help="'Main focus this quarter' from the PMF page (read-only)"),
            "Runway flag": st.column_config.TextColumn(
                help="Worked out from Runway (read-only). Red under 6 months, amber 6-12. Updates on save."),
            "Since check-in": st.column_config.TextColumn(
                help="Worked out from Last check-in (read-only). Amber after 45 days, red after 60."),
            "Stage": st.column_config.SelectboxColumn(options=db.STAGES),
            "Last fundraise": st.column_config.TextColumn(help="e.g. Seed, US$1.5M, Mar 2025"),
            "Runway (months)": st.column_config.NumberColumn(min_value=0, step=0.5, format="%g"),
            "Industry": st.column_config.SelectboxColumn(options=db.INDUSTRIES),
            "Sector": st.column_config.TextColumn(help="Sub-sector"),
            "Country": st.column_config.SelectboxColumn(options=db.COUNTRIES),
            "Last check-in": st.column_config.DateColumn(format="D MMM YYYY", max_value=date.today()),
            "Raise": st.column_config.TextColumn(help="Current or planned raise"),
            "Notes": st.column_config.TextColumn(width="large"),
        },
    )

    changed = [cid for cid in shown_df.index if row_values(shown_df.loc[cid]) != row_values(edited.loc[cid])]
    with st.container(horizontal=True, vertical_alignment="center"):
        save = st.button("Save changes", type="primary", disabled=not changed)
        if changed:
            st.caption(f"{plural(len(changed), 'row', 'rows')} changed and not yet saved. "
                       "Save before searching, filtering or sorting, or the edits will be lost.")
    if save:
        blank = [cid for cid in changed if not clean(edited.loc[cid, "Company name"])]
        clashes = duplicate_names(companies, {cid: clean(edited.loc[cid, "Company name"]) for cid in changed})
        if blank:
            st.error("Every company needs a name. Fill in the blank name and save again.")
        elif clashes:
            st.error(f"Company names must be unique. Another company is already called: {', '.join(clashes)}. "
                     "Change the name and save again.")
        else:
            for cid in changed:
                db.update_company(int(cid), row_values(edited.loc[cid]))
            flash(f"Changes saved ({plural(len(changed))})")
            bump()
            st.rerun()

    st.divider()
    checkin_section(companies)
    delete_section(companies)
    clear_section(companies)


def empty_state():
    with st.container(key="empty_state"):
        st.subheader("Add your first company")
        st.markdown("Add companies one by one, or import your portfolio from a CSV.")
        with st.container(horizontal=True):
            if st.button("Add company", type="primary", key="empty_add"):
                add_company_dialog()
            if st.button("Import CSV", key="empty_import"):
                import_dialog()


def checkin_section(companies):
    names = {c["id"]: picker_label(c) for c in companies}
    pick, go = st.columns([3, 1], vertical_alignment="bottom")
    company_id = pick.selectbox("Log a check-in", list(names), index=None, format_func=names.get,
                                placeholder="Choose a company")
    if go.button("Log check-in today", disabled=company_id is None, width="stretch"):
        db.update_company(company_id, {"last_checkin": date.today().isoformat()})
        flash(f"Check-in logged: {names[company_id]}")
        bump()
        st.rerun()


def clear_section(companies):
    with st.expander("Clear all data"):
        st.markdown(f"This permanently deletes all {plural(len(companies))} and all PMF data. "
                    "It can't be undone, so use **Export CSV** first if you want a copy.")
        typed = st.text_input("Type CLEAR to confirm", key=f"clear_confirm_{st.session_state.get('ver', 0)}",
                              placeholder="CLEAR")
        if st.button("Clear all data", disabled=typed.strip() != "CLEAR", key="clear_all"):
            db.clear_all()
            for key in ("pmf_company", "pmf_picker"):
                st.session_state.pop(key, None)
            flash("All data cleared")
            bump()
            st.rerun()


def delete_section(companies):
    names = {c["id"]: picker_label(c) for c in companies}
    with st.expander("Delete a company"):
        company_id = st.selectbox("Company to delete", list(names), index=None, format_func=names.get,
                                  placeholder="Choose a company", key=f"delete_pick_{st.session_state.get('ver', 0)}")
        if company_id is not None:
            sure = st.checkbox(f"Yes, permanently delete {names[company_id]} and its PMF notes")
            if st.button("Delete company", disabled=not sure):
                db.delete_company(company_id)
                flash(f"Company deleted: {names[company_id]}")
                bump()
                st.rerun()


pg = st.navigation([
    st.Page(portfolio_page, title="Portfolio", default=True),
    st.Page("views/pmf.py", title="PMF", url_path="PMF"),
], position="top")
pg.run()
