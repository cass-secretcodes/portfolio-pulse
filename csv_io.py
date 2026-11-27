"""CSV import and export for the Portfolio page.

Import rules:
- Columns are matched by header name (case-insensitive). Unknown columns are ignored.
- Blank cells mean "no data": they never overwrite an existing value. A real 0 is kept.
- A company whose name already exists (case-insensitive) is updated, not duplicated.
- A value that isn't allowed is skipped with a message naming the row, column and allowed values.
- Test hypothesis / Recommended test / Test due add one tactical-plan row, never the same row twice.
"""
import io
from datetime import date

import pandas as pd

import db

# Export / template column order.
COLUMNS = ["Company name", "Founder", "Stage", "Last fundraise", "Runway (months)", "Industry", "Sector",
           "Last check-in", "Raise", "Notes", "Country", "Status", "PMF stage", "Founder's focus", "Target market",
           "Customer conversations (30 days)", "Experiments this quarter", "PMF evidence", "Test hypothesis",
           "Recommended test", "Test due"]

# header (lower case) -> (where it goes, field name, how to check it)
FIELDS = {
    "company name": ("company", "name", "text"),
    "founder": ("company", "founder", "text"),
    "stage": ("company", "stage", db.STAGES),
    "last fundraise": ("company", "last_fundraise", "text"),
    "runway (months)": ("company", "runway_months", "runway"),
    "industry": ("company", "industry", db.INDUSTRIES),
    "sector": ("company", "sector", "text"),
    "last check-in": ("company", "last_checkin", "past_date"),
    "raise": ("company", "raise", "text"),
    "notes": ("company", "notes", "text"),
    "country": ("company", "country", db.COUNTRIES),
    "status": ("company", "status", db.STATUSES),
    "pmf stage": ("pmf", "pmf_stage", db.PMF_STAGES),
    "founder's focus": ("pmf", "main_focus", db.FOCUS_OPTIONS),
    "main focus this quarter": ("pmf", "main_focus", db.FOCUS_OPTIONS),  # same field as Founder's focus
    "target market": ("pmf", "target_market", "text"),
    "customer conversations (30 days)": ("pmf", "customer_conversations", "count"),
    "experiments this quarter": ("pmf", "experiments_run", "count"),
    "pmf evidence": ("pmf", "evidence_notes", "text"),
    "test hypothesis": ("test", "Hypothesis", "text"),
    "recommended test": ("test", "Test", "text"),
    "test due": ("test", "Due date", "any_date"),
}


def _header_key(header):
    return str(header).strip().replace("’", "'").lower()  # accept curly apostrophes from Excel


def _parse_date(value):
    """YYYY-MM-DD, or day-first dates such as 15/03/2025. Returns ISO text or None."""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
        return None if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _check(value, kind, row, column):
    """Return (clean value, problem message or None). Value is None when the field should be skipped."""
    if isinstance(kind, list):
        match = next((o for o in kind if o.lower() == value.lower()), None)
        if match is None:
            return None, (f"Row {row}, column '{column}': '{value}' is not an allowed value, so it was skipped. "
                          f"Allowed: {', '.join(kind)}.")
        return match, None
    if kind == "text":
        return value, None
    if kind in ("runway", "count"):
        number = pd.to_numeric(value, errors="coerce")
        if pd.isna(number) or number < 0 or (kind == "count" and number != int(number)):
            need = "a whole number, 0 or more" if kind == "count" else "a number of months, 0 or more"
            return None, f"Row {row}, column '{column}': '{value}' is not {need}, so it was skipped."
        return (int(number) if kind == "count" else float(number)), None
    parsed = _parse_date(value)
    if parsed is None:
        return None, (f"Row {row}, column '{column}': '{value}' is not a date (use YYYY-MM-DD or DD/MM/YYYY), "
                      "so it was skipped.")
    if kind == "past_date" and parsed > date.today().isoformat():
        return None, f"Row {row}, column '{column}': '{value}' is in the future, so it was skipped."
    return parsed, None


def parse(upload):
    """Read a CSV file. Returns (records, problems).

    Each record: {"row", "name", "company": {...}, "pmf": {...}, "test": {...} or None}, holding only
    non-blank, valid values.
    """
    try:
        df = pd.read_csv(upload, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception as e:  # unreadable file: report it, never crash
        return [], [f"Couldn't read that file as a CSV ({e})."]
    columns = [(col, FIELDS[_header_key(col)]) for col in df.columns if _header_key(col) in FIELDS]
    if not any(spec[1] == "name" for _, spec in columns):
        return [], ["The file needs a 'Company name' column. Download the template to see the headers."]
    unknown = [str(c) for c in df.columns if _header_key(c) not in FIELDS]
    problems = [f"Ignored column(s) the app doesn't use: {', '.join(unknown)}."] if unknown else []

    by_name = {}
    for i, raw in df.iterrows():
        row = i + 2  # spreadsheet row number (the header is row 1)
        rec = {"row": row, "company": {}, "pmf": {}, "test": {}}
        for col, (target, field, kind) in columns:
            value = str(raw[col]).strip()
            if not value or field in rec[target]:  # blank = no data; first of two focus columns wins
                continue
            clean, problem = _check(value, kind, row, col)
            if problem:
                problems.append(problem)
            elif clean is not None:
                rec[target][field] = clean
        name = rec["company"].get("name")
        if not name:
            if any(rec[t] for t in ("company", "pmf", "test")):
                problems.append(f"Row {row}: skipped because it has no company name.")
            continue
        rec["name"] = name
        rec["test"] = rec["test"] or None
        key = name.lower()
        if key in by_name:  # same company twice in one file: later non-blank values win
            problems.append(f"Row {row}: {name} also appears on row {by_name[key]['row']}; the rows were combined.")
            earlier = by_name[key]
            earlier["company"].update(rec["company"])
            earlier["pmf"].update(rec["pmf"])
            earlier["test"] = rec["test"] or earlier["test"]
        else:
            by_name[key] = rec
    return list(by_name.values()), problems


def _test_key(test):
    return tuple((test.get(k) or "").strip().lower() for k in ("Hypothesis", "Test", "Due date"))


def apply(records):
    """Write parsed records to the database. Returns counts for the confirmation message."""
    existing = {c["name"].strip().lower(): c["id"] for c in db.list_companies()}
    counts = {"added": 0, "updated": 0, "tests_added": 0}
    for rec in records:
        cid = existing.get(rec["name"].lower())
        if cid is None:
            cid = db.add_company(rec["company"])
            existing[rec["name"].lower()] = cid
            counts["added"] += 1
        else:
            changes = {k: v for k, v in rec["company"].items() if k != "name"}  # keep the existing spelling
            db.update_company(cid, changes)
            counts["updated"] += 1
        if rec["pmf"]:
            db.save_pmf(cid, rec["pmf"])
        if rec["test"]:
            tests = db.get_pmf(cid).get("tests", [])
            if _test_key(rec["test"]) not in {_test_key(t) for t in tests}:
                tests.append({"Hypothesis": rec["test"].get("Hypothesis"), "Test": rec["test"].get("Test"),
                              "Owner": "Founder", "Due date": rec["test"].get("Due date"), "Result": None})
                db.save_pmf(cid, {"tests": tests})
                counts["tests_added"] += 1
    return counts


def preview(records):
    """A small table showing what an import will do."""
    existing = {c["name"].strip().lower() for c in db.list_companies()}
    return pd.DataFrame([{
        "Company name": r["name"],
        "Action": "Update" if r["name"].lower() in existing else "Add",
        "Status": r["company"].get("status", ""),
        "Stage": r["company"].get("stage", ""),
        "PMF stage": r["pmf"].get("pmf_stage", ""),
        "Founder's focus": r["pmf"].get("main_focus", ""),
        "Test": "Yes" if r["test"] else "",
    } for r in records])


def _num(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return f"{value:g}" if isinstance(value, float) else str(value)


def export_rows(companies):
    rows = []
    for c in companies:
        pmf = db.get_pmf(c["id"])
        test = (pmf.get("tests") or [{}])[0]  # the first tactical-plan row
        rows.append({
            "Company name": c["name"], "Founder": c.get("founder") or "", "Stage": c.get("stage") or "",
            "Last fundraise": c.get("last_fundraise") or "", "Runway (months)": _num(c.get("runway_months")),
            "Industry": c.get("industry") or "", "Sector": c.get("sector") or "",
            "Last check-in": c.get("last_checkin") or "", "Raise": c.get("raise") or "", "Notes": c.get("notes") or "",
            "Country": c.get("country") or "", "Status": c.get("status") or "",
            "PMF stage": db.OLD_PMF_STAGES.get(pmf.get("pmf_stage"), pmf.get("pmf_stage")) or "",
            "Founder's focus": pmf.get("main_focus") or "", "Target market": pmf.get("target_market") or "",
            "Customer conversations (30 days)": _num(pmf.get("customer_conversations")),
            "Experiments this quarter": _num(pmf.get("experiments_run")),
            "PMF evidence": pmf.get("evidence_notes") or "",
            "Test hypothesis": test.get("Hypothesis") or "", "Recommended test": test.get("Test") or "",
            "Test due": test.get("Due date") or "",
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")  # BOM so Excel reads accents correctly


def template_bytes():
    return to_csv_bytes(pd.DataFrame(columns=COLUMNS))


def export_bytes(companies):
    return to_csv_bytes(export_rows(companies))


def parse_path(path):
    with open(path, "rb") as f:
        return parse(io.BytesIO(f.read()))
