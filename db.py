"""SQLite storage for the portfolio dashboard. The database is created automatically if missing."""
import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio.db")

STAGES = ["Pre-seed", "Seed", "Series A", "Series B+", "Other"]
INDUSTRIES = ["AI", "Software", "Critical & deep tech", "Climate", "Other"]
COUNTRIES = ["Australia", "Singapore", "Indonesia", "Malaysia", "Vietnam", "Philippines", "Thailand",
             "India", "Japan", "New Zealand", "United States", "Other"]
STATUSES = ["Green", "Amber", "Red"]
FOCUS_OPTIONS = ["Test market demand", "Customer interviews", "Develop new feature", "Pricing and packaging",
                 "Fundraising", "Hiring", "Operations", "Other"]
# Earlier focus options, mapped to the closest current one on startup.
OLD_FOCUS_OPTIONS = {"Customers and experiments": "Customer interviews", "Product build": "Develop new feature"}
PMF_STAGES = ["Pre-validation", "Early signs of PMF", "Clear evidence of PMF"]
# Earlier versions saved longer labels; these are mapped to the short ones on startup.
OLD_PMF_STAGES = {
    "Pre-validation (still in the valley of validation)": "Pre-validation",
    "Early signs of PMF (what seed investors look for)": "Early signs of PMF",
    "Clear evidence of PMF (what Series A investors look for)": "Clear evidence of PMF",
}

# Database column -> label shown in the app (and used as CSV headers).
COMPANY_FIELDS = {
    "name": "Company name",
    "status": "Status",
    "founder": "Founder",
    "stage": "Stage",
    "last_fundraise": "Last fundraise",
    "runway_months": "Runway (months)",
    "industry": "Industry",
    "sector": "Sector",
    "country": "Country",
    "last_checkin": "Last check-in",
    "raise": "Raise",
    "notes": "Notes",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    founder TEXT,
    stage TEXT,
    last_fundraise TEXT,
    runway_months REAL,
    industry TEXT,
    sector TEXT,
    last_checkin TEXT,      -- ISO date, YYYY-MM-DD
    raise TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS pmf (
    company_id INTEGER PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    pmf_stage TEXT,
    demand_repeatable INTEGER DEFAULT 0,
    unit_economics_positive INTEGER DEFAULT 0,
    customer_group_large INTEGER DEFAULT 0,
    icp_defined INTEGER DEFAULT 0,
    founder_talks_to_customers INTEGER DEFAULT 0,
    evidence_notes TEXT,
    milestones TEXT,
    success_indicators TEXT,
    critical_numbers TEXT,  -- JSON list of {Metric, Target, Current}
    tests TEXT,             -- JSON list of {Hypothesis, Test, Owner, Due date, Result}
    founder_time_pct INTEGER,  -- no longer used (replaced by the founder focus fields)
    team_headspace TEXT,
    strategic_advice TEXT,
    last_reviewed TEXT      -- ISO date
);
"""

PMF_JSON_FIELDS = ("critical_numbers", "tests")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """Bring older databases up to date. Safe to run every time."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(companies)")}
    if "status" not in columns:
        conn.execute("ALTER TABLE companies ADD COLUMN status TEXT")  # Green / Amber / Red
    if "country" not in columns:
        conn.execute("ALTER TABLE companies ADD COLUMN country TEXT")
    pmf_columns = {row["name"] for row in conn.execute("PRAGMA table_info(pmf)")}
    if "target_market" not in pmf_columns:
        conn.execute("ALTER TABLE pmf ADD COLUMN target_market TEXT")
    # Founder focus fields (these replace the old founder_time_pct slider, which is no longer used)
    for column, kind in [("main_focus", "TEXT"), ("customer_conversations", "INTEGER"), ("experiments_run", "INTEGER")]:
        if column not in pmf_columns:
            conn.execute(f"ALTER TABLE pmf ADD COLUMN {column} {kind}")
    for old, new in OLD_FOCUS_OPTIONS.items():
        conn.execute("UPDATE pmf SET main_focus = ? WHERE main_focus = ?", (new, old))
    for old, new in OLD_PMF_STAGES.items():
        conn.execute("UPDATE pmf SET pmf_stage = ? WHERE pmf_stage = ?", (new, old))
    conn.commit()


# ---------------------------------------------------------------- companies

def list_companies():
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.*, p.pmf_stage, p.main_focus FROM companies c LEFT JOIN pmf p ON p.company_id = c.id "
            "ORDER BY c.name COLLATE NOCASE")
        return [dict(r) for r in rows]


def get_company(company_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        return dict(row) if row else None


def add_company(values):
    cols = [c for c in COMPANY_FIELDS if c in values]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO companies ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [values[c] for c in cols],
        )
        return cur.lastrowid


def update_company(company_id, values):
    cols = [c for c in COMPANY_FIELDS if c in values]
    if not cols:
        return
    with connect() as conn:
        conn.execute(
            f"UPDATE companies SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
            [values[c] for c in cols] + [company_id],
        )


def delete_company(company_id):
    with connect() as conn:
        conn.execute("DELETE FROM pmf WHERE company_id = ?", (company_id,))
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))


def clear_all():
    """Delete every company and all PMF data, in one transaction."""
    with connect() as conn:
        conn.execute("DELETE FROM pmf")
        conn.execute("DELETE FROM companies")


# ---------------------------------------------------------------- PMF

def get_pmf(company_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM pmf WHERE company_id = ?", (company_id,)).fetchone()
    if not row:
        return {}
    data = dict(row)
    for f in PMF_JSON_FIELDS:
        data[f] = json.loads(data[f]) if data.get(f) else []
    return data


def save_pmf(company_id, values):
    data = dict(values)
    for f in PMF_JSON_FIELDS:
        if f in data:
            data[f] = json.dumps(data[f])
    cols = list(data)
    with connect() as conn:
        conn.execute(
            f"INSERT INTO pmf (company_id, {', '.join(cols)}) VALUES (?, {', '.join('?' for _ in cols)}) "
            f"ON CONFLICT(company_id) DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in cols)}",
            [company_id] + [data[c] for c in cols],
        )
