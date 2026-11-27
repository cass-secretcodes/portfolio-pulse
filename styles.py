"""The app's single source of visual style: colour tokens, injected CSS and small HTML helpers.

Theme basics (dark base, fonts, radius, borders) live in .streamlit/config.toml and mirror these tokens.
Everything here is presentation only.
"""
import html

import streamlit as st

# ---------------------------------------------------------------- colour tokens
PAGE = "#141A26"
SURFACE = "#1B2230"      # stat tiles, empty state, dialogs, table background
RAISED = "#232C3D"       # inputs, dropdowns, hovered rows
BORDER = "#2E384C"       # hairline borders
TEXT = "#E8ECF4"
MUTED = "#9AA6BD"        # captions, labels
PRIMARY = "#607196"      # primary buttons
ACCENT = "#8EA0C7"       # links, active nav, focus rings, secondary hover
GREEN = "#5CBF93"
AMBER = "#E0A93B"
RED = "#E27A7A"
RADIUS = "4px"


def _tint(hex_colour, alpha):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


# Status as coloured text on a faint (15%) tint of the same colour - used for read-only table cells.
CELL_RED = f"color: {RED}; background-color: {_tint(RED, 0.15)}"
CELL_AMBER = f"color: {AMBER}; background-color: {_tint(AMBER, 0.15)}"
CELL_GREEN = f"color: {GREEN}; background-color: {_tint(GREEN, 0.15)}"

# Editable Status pills: Streamlit picks the pill text colour itself, so the pill gets a slightly
# stronger tint (about 35%) to stay clearly coloured while the text stays readable.
STATUS_PILL_COLOURS = {"Green": GREEN + "59", "Amber": AMBER + "59", "Red": RED + "59"}


# ---------------------------------------------------------------- CSS
CSS = f"""
<style>
/* ---- Developer chrome ---- */
footer, [data-testid="stFooter"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none !important; }}

/* ---- Flat look: separate layers with colour and borders, never shadows ---- */
*, *::before, *::after {{ box-shadow: none !important; }}

/* ---- Header with wordmark and top navigation ---- */
header[data-testid="stHeader"] {{
    background: {PAGE}; border-bottom: 1px solid {BORDER}; height: 3.5rem;
}}
/* Line the nav text up with the page title: the toolbar's inner wrappers add 16px and each link 8px */
[data-testid="stToolbar"] {{ padding-left: 0; margin-left: calc(3rem - 24px); padding-right: 3rem; height: 3.5rem; }}
[data-testid="stTopNavLink"] {{ border-radius: {RADIUS}; background: transparent; }}
[data-testid="stTopNavLink"] span {{ color: {MUTED}; font-weight: 500; }}
[data-testid="stTopNavLink"]:hover {{ background: {RAISED}; }}
[data-testid="stTopNavLink"]:hover span {{ color: {TEXT}; }}
[data-testid="stTopNavLink"][aria-current] {{ background: {_tint(ACCENT, 0.14)}; }}
[data-testid="stTopNavLink"][aria-current] span {{ color: {ACCENT}; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}

/* ---- Page layout ---- */
[data-testid="stMainBlockContainer"] {{ padding: 5.5rem 3rem 4rem; max-width: none; }}
@media (max-width: 900px) {{
    [data-testid="stMainBlockContainer"] {{ padding: 5rem 1.25rem 3rem; }}
    [data-testid="stToolbar"] {{ margin-left: calc(1.25rem - 24px); padding-right: 1.25rem; }}
}}
h1, h2, h3, h4, h5, h6 {{ font-weight: 600 !important; letter-spacing: -0.01em; }}
h1 {{ padding: 0 !important; font-size: 1.75rem !important; }}
strong, b {{ font-weight: 600; }}
th {{ font-weight: 500; }}
input, textarea, [data-baseweb="select"] {{ font-variant-numeric: tabular-nums; }}
a {{ color: {ACCENT}; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: {MUTED} !important; }}
[data-testid="stWidgetLabel"] p {{ color: {MUTED}; font-weight: 500; }}

/* ---- Focus rings ---- */
*:focus-visible {{ outline: 2px solid {ACCENT} !important; outline-offset: 2px; }}

/* ---- Buttons ---- */
button[data-testid^="stBaseButton-primary"] {{
    background: {PRIMARY}; border: 1px solid {PRIMARY}; color: #FFFFFF;
}}
button[data-testid^="stBaseButton-primary"]:hover {{ background: #6B7CA3; border-color: {ACCENT}; color: #FFFFFF; }}
button[data-testid^="stBaseButton-primary"]:disabled {{ background: {RAISED}; border-color: {BORDER}; color: {MUTED}; }}
button[data-testid^="stBaseButton-secondary"] {{
    background: transparent; border: 1px solid {BORDER}; color: {TEXT};
}}
button[data-testid^="stBaseButton-secondary"]:hover {{ background: transparent; border-color: {ACCENT}; color: {TEXT}; }}
button[data-testid^="stBaseButton-secondary"]:disabled {{ color: {MUTED}; border-color: {BORDER}; }}
button[data-testid^="stBaseButton"]:not([data-testid="stBaseButton-elementToolbar"]):not([data-testid="stBaseButton-headerNoPadding"]) {{
    min-width: 7.5rem; min-height: 36px; height: 36px; padding: 0 16px; line-height: 1;
}}
button[data-testid^="stBaseButton"] p {{ white-space: nowrap; font-weight: 500; }}

.st-key-pmf_map_notes {{ margin-bottom: 1.25rem; }}

/* ---- Inputs, selects, text areas, date and number inputs ---- */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div, [data-testid="stNumberInputContainer"] {{
    background-color: {RAISED} !important; border-color: {BORDER} !important;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within,
[data-baseweb="select"] > div:focus-within {{ border-color: {ACCENT} !important; }}
input, textarea {{ color: {TEXT} !important; caret-color: {ACCENT}; }}
input::placeholder, textarea::placeholder {{ color: {MUTED} !important; opacity: 1; }}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {{ background: {RAISED}; color: {TEXT}; }}
[data-baseweb="tag"] {{ background: {BORDER} !important; color: {TEXT} !important; }}

/* ---- Popover menus: select lists and date pickers (both pages, dialogs included) ---- */
[data-baseweb="popover"] {{ background: transparent !important; }}
[data-baseweb="popover"] > div, [data-baseweb="menu"], ul[role="listbox"],
[data-testid="stSelectboxVirtualDropdown"] {{
    background: {RAISED} !important; border-radius: {RADIUS};
}}
[data-baseweb="popover"] > div {{ border: 1px solid {BORDER}; }}
li[role="option"] {{ color: {TEXT}; }}
li[role="option"]:hover, li[role="option"][aria-selected="true"] {{ background: {BORDER} !important; }}
[data-baseweb="calendar"], [data-baseweb="calendar"] > div, [data-baseweb="datepicker"] {{
    background: {RAISED} !important; color: {TEXT};
}}
/* Blank days before the 1st of the month have no label; hide their page-coloured fill */
[data-baseweb="calendar"] [role="gridcell"]:not([aria-label])::after {{ background-color: transparent !important; }}

/* ---- Surfaces: expanders, dialogs, bordered containers, uploader, toasts ---- */
[data-testid="stExpander"] details {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS}; }}
[data-testid="stExpander"] summary:hover p {{ color: {ACCENT}; }}
div[role="dialog"] {{ background: {SURFACE} !important; border: 1px solid {BORDER}; border-radius: {RADIUS}; }}
[data-testid="stFileUploaderDropzone"] {{ background: {RAISED}; border: 1px dashed {BORDER}; border-radius: {RADIUS}; }}
[data-testid="stToast"] {{ background: {RAISED} !important; border: 1px solid {BORDER}; color: {TEXT}; }}
[data-testid="stAlertContainer"] {{ border-radius: {RADIUS}; }}
hr {{ border-color: {BORDER} !important; }}
[data-testid="stCheckbox"] p {{ color: {TEXT}; font-weight: 400; }}

/* ---- Tables (data editor overlay editors and toolbar) ---- */
[data-testid="stDataFrame"] {{ border-radius: {RADIUS}; }}
[data-testid="stElementToolbar"] button {{ background: {SURFACE}; color: {MUTED}; min-width: 0; }}
.gdg-overlay-editor, #portal > div > div {{ color: {TEXT}; }}

/* ---- Custom blocks ---- */
.pp-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 1.25rem 0 0.75rem; }}
.pp-stat {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS}; padding: 14px 16px; }}
.pp-stat .label {{ color: {MUTED}; font-size: 0.8125rem; font-weight: 500; }}
.pp-stat .value {{ color: {TEXT}; font-size: 1.6rem; font-weight: 600; line-height: 1.3; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.st-key-empty_state, .st-key-pmf_strip {{
    background: {SURFACE}; border: 1px solid {BORDER} !important; border-radius: {RADIUS}; padding: 1.5rem;
}}
.st-key-empty_state {{ margin-top: 1.25rem; }}
.st-key-empty_state h3 {{ margin: 0; padding: 0; }}
.st-key-pmf_strip {{ padding: 1rem 1.25rem; }}
.pp-count {{ color: {MUTED}; font-size: 0.875rem; margin-top: 0.15rem; }}
</style>
"""


def apply():
    """Inject the shared CSS. Call once per run, before any page content."""
    st.markdown(CSS, unsafe_allow_html=True)


def stat_tiles(items):
    """items: list of (label, value). Renders a row of small surface tiles."""
    tiles = "".join(
        f'<div class="pp-stat"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(str(value))}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="pp-stats">{tiles}</div>', unsafe_allow_html=True)


def muted(text):
    st.markdown(f'<div class="pp-count">{html.escape(text)}</div>', unsafe_allow_html=True)
