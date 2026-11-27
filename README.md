# Portfolio dashboard

A simple working dashboard for the portfolio team: one editable table of companies, plus a
product-market fit (PMF) page per company. Built with Streamlit and SQLite.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The database (`portfolio.db`) is created automatically the first time the app runs, and starts empty.
Back it up by copying that file.

## Deploy (Streamlit Community Cloud)

1. Push this repository to GitHub (a private repository is fine).
2. On share.streamlit.io, create an app from the repository with **Main file path** `app.py`.
   Under *Advanced settings*, pick Python 3.11 or 3.12.
3. The app starts empty. Testers add companies or use **Import CSV**.

Data storage on Community Cloud - please read before inviting testers:
- The SQLite file lives on the app's temporary disk. It is **wiped whenever the app restarts, sleeps or
  is redeployed**, so treat it as scratch space; use **Export CSV** to keep anything.
- There is **one shared database for everyone** using the app: testers see each other's companies.
  Ask testers to use dummy or anonymised data, or give each tester their own deployment.

## Pages

**Portfolio** (`app.py`)
- One table of every company. Click any cell to edit it, then press **Save changes**.
- **Status** (Green / Amber / Red) is set by the team in the table or the Add company form.
- Read-only columns, worked out automatically:
  - **PMF**: the stage saved on the PMF page.
  - **Runway flag**: red under 6 months, amber 6-12. Refreshes when you save.
  - **Days since check-in**: amber over 45 days, red over 60.
- Search by company or founder; filter by stage, industry and country. **Sort by** company name, status (red first)
  or days since check-in (longest first), or click a column header.
- **Add company** opens a form. Company name is required and must be unique (this is also checked
  when you rename a company in the table). Check-in dates can't be in the future.
- **Log a check-in** sets a company's last check-in to today in one click.
- **Delete a company** is in an expander and needs a confirmation tick.
- **Import CSV** and **Export CSV** (top right). Export and the downloadable template use the same 21
  columns: the 10 core columns, then Country, Status, PMF stage,
  Founder's focus, Target market, Customer conversations (30 days), Experiments this quarter, PMF evidence,
  Test hypothesis, Recommended test and Test due. Import rules:
  - Only Company name is required. Columns are matched by header; unknown columns are ignored.
    "Main focus this quarter" is accepted as another name for "Founder's focus".
  - A company that already exists (any capitalisation) is updated, never duplicated. Blank cells never
    overwrite saved values; a real 0 is kept. Importing the same file twice is safe.
  - Values that aren't allowed (Stage, Industry, Status, PMF stage, Founder's focus, Country), negative
    numbers, bad dates and future check-in dates are skipped, with a message giving the row and column.
  - Test hypothesis / Recommended test / Test due add one row to the company's tactical plan
    (Owner "Founder"), never the same row twice. Export includes each company's first tactical-plan row.

**PMF** (`views/pmf.py`)
- **PMF map** at the top: an illustrative startup-journey curve with each assessed company as a dot, placed by
  its PMF stage (valley, rising slope or near the peak) and coloured by Status. Hover a dot for details.
  Companies with no PMF stage yet are counted under the chart. Each dot's spot
  comes from the company name, so it doesn't move between visits.
- Pick a company to see its stage, runway and last check-in.
- Four sections, based on the Wavemaker Impact *Portfolio Acceleration* whitepaper (Nov 2024): where the
  company is on PMF, the strategic plan, the tactical plan (minimum viable tests), and founder focus.
- **Save** stores everything and sets "PMF last reviewed" to today.

## Files

| File | Purpose |
|---|---|
| `app.py` | Portfolio page; also sets up the two-page navigation |
| `views/pmf.py` | PMF page |
| `db.py` | SQLite tables and read/write helpers |
| `csv_io.py` | CSV import and export rules |
| `pmf_map.py` | The PMF map chart (Plotly) |
| `styles.py` | All visual styling: colour tokens and the CSS that gives the app its dark look |
| `.streamlit/config.toml` | Theme settings (dark colours, fonts, corner radius) - kept in step with `styles.py` |
| `requirements.txt` | Python packages |
