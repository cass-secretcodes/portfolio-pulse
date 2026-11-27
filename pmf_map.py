"""PMF map: an illustrative startup-journey curve with each company placed by its saved PMF stage.

Positions are illustrative, not measured: each PMF stage maps to a stretch of the curve, and each company
gets a stable spot within its stretch, derived from its name and spread evenly (so dots don't move between
refreshes and don't pile up).
"""
import hashlib
import math
from datetime import date

import plotly.graph_objects as go

import styles

# Curve shape: a small first peak, the valley of validation, then a rise to the proven-market peak.
PEAK_X = 8.6
X_POINTS = [i * PEAK_X / 300 for i in range(301)]

# Each PMF stage is drawn along its own stretch of the curve (x range).
STAGE_RANGES = {
    "Pre-validation": (2.9, 5.3),          # along the valley
    "Early signs of PMF": (5.7, 7.4),      # on the rising slope
    "Clear evidence of PMF": (7.6, 8.6),   # near the peak
}
Y_FLOOR = -0.22  # bottom of the chart; the shaded region runs from here up to the curve
STATUS_COLOURS = {"Green": styles.GREEN, "Amber": styles.AMBER, "Red": styles.RED}


def curve(x):
    bump = 0.28 * math.exp(-((x - 2.0) / 0.85) ** 2)
    rise = 0.95 * math.exp(-((x - PEAK_X) / 2.2) ** 2)
    return 0.08 + bump + rise


def _hash_fraction(text, salt=""):
    """A stable number in [0, 1) from the text - the same name always gives the same value."""
    digest = hashlib.sha256((salt + text.strip().lower()).encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / 16 ** 12


def positions(companies):
    """{company name: (x, y)} for every company with a PMF stage.

    Within each stage's stretch, a company's spot is half its own name-based position and half an even
    share of the stretch (ordered by that same name-based value). Nothing is random, so dots stay put
    between refreshes, and the even share stops them bunching up on top of each other.
    """
    out = {}
    for stage, (lo, hi) in STAGE_RANGES.items():
        names = sorted((c["name"] for c in companies if c.get("pmf_stage") == stage), key=_hash_fraction)
        for rank, name in enumerate(names):
            own = _hash_fraction(name)
            even = (rank + 0.5) / len(names)
            x = lo + (0.5 * own + 0.5 * even) * (hi - lo)
            # A small, stable nudge either side of the line so neighbours overlap less.
            out[name] = (x, curve(x) + (_hash_fraction(name, "y") - 0.5) * 0.05)
    return out


def _nice_date(iso):
    if not iso:
        return "Not yet"
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def build_figure(companies):
    """companies: dicts with name, status, pmf_stage, country, runway_months, last_checkin."""
    fig = go.Figure()
    xs = X_POINTS
    ys = [curve(x) for x in xs]

    # Lightly shaded "Early stage" region under the curve, up to the proven-market peak.
    fig.add_trace(go.Scatter(x=xs, y=[Y_FLOOR] * len(xs), mode="lines", line=dict(width=0),
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(142, 160, 199, 0.06)", hoverinfo="skip", showlegend=False))
    # The journey line itself.
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=styles.MUTED, width=1.5),
                             hoverinfo="skip", showlegend=False))

    dots = []
    spots = positions(companies)
    for c in companies:
        pos = spots.get(c["name"])
        if pos is None:
            continue
        runway = c.get("runway_months")
        dots.append({
            "x": pos[0], "y": pos[1],
            "colour": STATUS_COLOURS.get(c.get("status"), styles.MUTED),
            "info": [c["name"], c["pmf_stage"], c.get("country") or "Not set",
                     f"{runway:g} months" if runway is not None else "Not set", _nice_date(c.get("last_checkin"))],
        })
    if dots:
        fig.add_trace(go.Scatter(
            x=[d["x"] for d in dots], y=[d["y"] for d in dots], mode="markers",
            marker=dict(size=12, color=[d["colour"] for d in dots], line=dict(color=styles.PAGE, width=1.5)),
            customdata=[d["info"] for d in dots], showlegend=False,
            hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Country: %{customdata[2]}"
                           "<br>Runway: %{customdata[3]}<br>Last check-in: %{customdata[4]}<extra></extra>"),
        ))

    label = dict(showarrow=False, font=dict(size=12, color=styles.MUTED))
    fig.add_annotation(x=4.0, y=curve(4.0) - 0.06, text="Valley of validation", yanchor="top", **label)
    fig.add_annotation(x=PEAK_X - 0.1, y=curve(PEAK_X) + 0.07, text="Proven market opportunity",
                       xanchor="right", yanchor="bottom", **label)
    fig.add_annotation(x=0.25, y=Y_FLOOR + 0.05, text="Early stage", xanchor="left", yanchor="bottom", **label)

    axis = dict(showgrid=False, zeroline=False, showticklabels=False, ticks="", showline=False,
                title_font=dict(size=12, color=styles.MUTED))
    fig.update_layout(
        height=320, margin=dict(l=36, r=12, t=12, b=36),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=styles.TEXT),
        xaxis=dict(title_text="Time and funding", range=[0, PEAK_X + 0.35], fixedrange=True, **axis),
        yaxis=dict(title_text="Value", range=[Y_FLOOR, 1.2], fixedrange=True, **axis),
        hoverlabel=dict(bgcolor=styles.RAISED, bordercolor=styles.BORDER,
                        font=dict(family="IBM Plex Sans, sans-serif", color=styles.TEXT, size=13)),
        showlegend=False,
    )
    return fig
