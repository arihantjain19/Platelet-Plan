"""PlateletPlan - Streamlit app.  Run:  streamlit run app.py"""
import html
import math
import pathlib

import altair as alt
import pandas as pd
import streamlit as st

import pp_config as C
from pp_data import travel_minutes
from pp_planner import build_system, daily_plan, plan_from_register

ROOT = pathlib.Path(__file__).resolve().parent
RES = ROOT  # all result files sit next to app.py

# Force the light theme so the design reads the same for every visitor (even in browser dark mode)
try:
    st._config.set_option("theme.base", "light")
    st._config.set_option("theme.primaryColor", "#A4161A")
except Exception:
    pass

st.set_page_config(page_title="PlateletPlan", page_icon="🩸", layout="wide", initial_sidebar_state="auto")

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
INK, STEEL, RULE, PAPER, CARD = "#1B1F27", "#5C6573", "#E4E7EC", "#F3F4F7", "#FFFFFF"
WINE, RED, STRAW, AMBER, ORANGE = "#3D0A10", "#A4161A", "#E3A73B", "#D98A2B", "#C4521F"
GOOD, GREY, SKY = "#2F6B4F", "#A9B0BA", "#2E5E8C"
LIFE_COLOURS = {5: "#EDC261", 4: STRAW, 3: AMBER, 2: ORANGE, 1: RED}  # days of life left
CENTRE_NAMES = {c.code: c.name.split(" - ")[1] for c in C.CENTRES}
CENTRE_LABEL = {c.code: f"Centre {c.code} · {c.name.split(' - ')[1]}" for c in C.CENTRES}

# small line icons (24px grid), drawn inline so nothing has to be downloaded
ICON = {
    "drop": '<path d="M12 2.5S5 10.2 5 15a7 7 0 0 0 14 0c0-4.8-7-12.5-7-12.5z"/>',
    "stack": '<rect x="4" y="13" width="16" height="7" rx="1.5"/><rect x="6" y="6" width="12" height="6" rx="1.5"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "pulse": '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>',
    "truck": '<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17.5" cy="17.5" r="1.8"/>',
    "calendar": '<rect x="4" y="5.5" width="16" height="14" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
    "map": '<path d="M9 4 3 6.5v13L9 17l6 2.5 6-2.5v-13L15 6.5 9 4zM9 4v13M15 6.5v13"/>',
    "chart": '<path d="M4 19h16M7 16v-5M12 16V7M17 16v-8"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "alert": '<path d="M12 4 2.8 19.5h18.4L12 4z"/><path d="M12 10v4.5M12 17.3v.2"/>',
}


def icon(name, size=20, color="currentColor", stroke=1.8):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON[name]}</svg>')


def bag(color, new=False, w=17, h=24):
    """A platelet bag: port on top, rounded body, label band."""
    if new:
        return (f'<svg class="bag" width="{w}" height="{h}" viewBox="0 0 17 24" aria-hidden="true">'
                f'<rect x="7" y="0.8" width="3" height="3.4" rx="1" fill="none" stroke="{INK}" stroke-width="1.1"/>'
                f'<rect x="1.2" y="4" width="14.6" height="19" rx="4" fill="none" stroke="{INK}" stroke-width="1.3" stroke-dasharray="2.4 1.8"/></svg>')
    return (f'<svg class="bag" width="{w}" height="{h}" viewBox="0 0 17 24" aria-hidden="true">'
            f'<rect x="7" y="0.5" width="3" height="4" rx="1" fill="{color}" opacity=".75"/>'
            f'<rect x="1" y="4" width="15" height="19.5" rx="4" fill="{color}"/>'
            f'<rect x="3.5" y="12" width="10" height="4.5" rx="1" fill="#fff" opacity=".55"/></svg>')


# subtle "platelet" pattern for the header band
PATTERN = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'>"
           "<g fill='none' stroke='white' stroke-opacity='0.09' stroke-width='1.5'>"
           "<ellipse cx='20' cy='24' rx='9' ry='5' transform='rotate(-20 20 24)'/>"
           "<ellipse cx='84' cy='18' rx='7' ry='4' transform='rotate(25 84 18)'/>"
           "<ellipse cx='60' cy='70' rx='10' ry='5.5' transform='rotate(10 60 70)'/>"
           "<ellipse cx='18' cy='96' rx='6' ry='3.5' transform='rotate(-35 18 96)'/>"
           "<ellipse cx='104' cy='92' rx='8' ry='4.5' transform='rotate(40 104 92)'/></g></svg>")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800;900&display=swap');
html, body, .stApp, [class*="css"], .stMarkdown, button, input, select, textarea {{ font-family: 'Public Sans', sans-serif !important; }}
.stApp {{ background: {PAPER}; color: {INK}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {RULE}; }}
[data-testid="stSidebar"] * {{ color: {INK}; }}
.block-container {{ padding-top: 1.6rem; max-width: 1280px; }}
h1, h2, h3, h4, p, li, label, span, div {{ color: {INK}; }}

/* tabs as a segmented control */
.stTabs [role="tablist"] {{ gap: .3rem !important; background:{CARD}; border:1px solid {RULE}; border-radius: 12px; padding: .3rem; width: fit-content; max-width:100%; flex-wrap: wrap; }}
.stTabs [data-testid="stTab"] {{ padding: .5rem 1rem !important; border-radius: 9px; height:auto !important; background: transparent; }}
.stTabs [data-testid="stTab"] p {{ font-weight: 700 !important; color: {STEEL} !important; margin:0; }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background: {WINE} !important; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color: #fff !important; }}
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none !important; }}
.stTabs [role="tabpanel"] {{ padding-top: 1rem; }}

/* header band */
.pp-hero {{ position:relative; overflow:hidden; border-radius: 20px; padding: 1.7rem 2rem 1.6rem; margin-bottom: 1.1rem;
  background: url("{PATTERN}"), linear-gradient(120deg, #2A060A 0%, {WINE} 38%, #7A111A 78%, {RED} 100%); }}
.pp-hero * {{ color:#fff !important; }}
.pp-hero .top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:1.5rem; flex-wrap:wrap; }}
.pp-hero .brand {{ display:flex; align-items:center; gap:.75rem; }}
.pp-hero .logo {{ width:44px; height:44px; border-radius:12px; background:rgba(255,255,255,.12); display:grid; place-items:center; }}
.pp-hero h1 {{ font-size: 2rem; font-weight: 900; letter-spacing:-0.03em; margin:0; line-height:1; }}
.pp-hero .tag {{ font-size: .98rem; opacity:.82; margin-top:.35rem; max-width: 60ch; }}
.pp-chips {{ display:flex; gap:.5rem; flex-wrap:wrap; justify-content:flex-end; }}
.pp-chip {{ display:inline-flex; align-items:center; gap:.45rem; background: rgba(255,255,255,.11); border:1px solid rgba(255,255,255,.18);
  padding:.45rem .75rem; border-radius: 999px; font-size:.88rem; font-weight:600; white-space:nowrap; }}
.pp-chip.alert {{ background: rgba(237,194,97,.22); border-color: rgba(237,194,97,.55); }}

/* cards */
.pp-card {{ background:{CARD}; border:1px solid {RULE}; border-radius:16px; padding:1.35rem 1.5rem;
  box-shadow: 0 1px 2px rgba(27,31,39,.04), 0 8px 24px -12px rgba(61,10,16,.18); }}
.pp-card .pp-h {{ font-size:1rem; font-weight:800; margin:0 0 .9rem 0; display:flex; align-items:center; gap:.5rem; }}
.pp-card .pp-h .ic {{ width:30px; height:30px; border-radius:9px; display:grid; place-items:center; background:#F7E9EA; color:{RED}; }}
.pp-card .pp-h .ic svg {{ stroke:{RED}; }}
.pp-card .pp-h .sub {{ font-weight:500; color:{STEEL}; font-size:.88rem; margin-left:auto; }}
.pp-grid {{ display:grid; grid-template-columns: 1.25fr 1fr; gap: 1.1rem; margin-bottom: 1.1rem; }}
.pp-grid2 {{ display:grid; grid-template-columns: 1.35fr 1fr; gap: 1.1rem; margin: 1.1rem 0; }}
.num {{ font-variant-numeric: tabular-nums; }}

/* decision */
.pp-dec {{ display:grid; grid-template-columns: auto 1fr; gap: 1.4rem; align-items:center; }}
.pp-ring {{ position:relative; width:170px; height:170px; }}
.pp-ring .c {{ position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
.pp-ring .n {{ font-size:3.6rem; font-weight:900; letter-spacing:-0.04em; line-height:1; font-variant-numeric: tabular-nums; }}
.pp-ring .u {{ font-size:.82rem; color:{STEEL}; font-weight:600; margin-top:.2rem; }}
.pp-verb {{ font-size:.95rem; font-weight:800; color:{RED}; margin-bottom:.25rem; }}
.pp-headline {{ font-size:1.45rem; font-weight:800; letter-spacing:-0.01em; line-height:1.25; }}
.pp-note {{ color:{STEEL}; margin-top:.5rem; font-size:.93rem; }}
.pp-calc {{ margin-top:.9rem; padding:.75rem .9rem; background:{PAPER}; border-radius:10px; font-size:.9rem; color:{STEEL}; }}
.pp-calc b {{ color:{INK}; font-variant-numeric: tabular-nums; }}
.pp-why {{ margin-top: 1.1rem; }}
.pp-why .t {{ font-size:.88rem; font-weight:700; color:{STEEL}; margin-bottom:.35rem; }}
.pp-reason {{ display:grid; grid-template-columns: 1fr auto; gap:1rem; align-items:center; padding:.5rem 0; border-bottom:1px solid {RULE}; font-size:.94rem; }}
.pp-reason:last-child {{ border-bottom:none; }}
.pp-reason .bar {{ height:6px; border-radius:3px; background:{RED}; opacity:.85; margin-top:.35rem; }}
.pp-reason .bar.down {{ background:{GOOD}; }}
.pp-reason .v {{ font-weight:800; font-variant-numeric: tabular-nums; white-space:nowrap; }}
.pp-reason .v.up {{ color:{RED}; }} .pp-reason .v.down {{ color:{GOOD}; }}

/* forecast + facts */
.pp-fbars {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:.8rem; align-items:end; height: 150px; margin-bottom:.4rem; }}
.pp-fbar {{ display:flex; flex-direction:column; justify-content:flex-end; align-items:center; height:100%; }}
.pp-fbar .val {{ font-size:1.5rem; font-weight:900; font-variant-numeric: tabular-nums; margin-bottom:.3rem; }}
.pp-fbar .col {{ width:100%; border-radius:10px 10px 4px 4px; background: linear-gradient(180deg, {RED} 0%, #C9474B 100%); }}
.pp-fbar.later .col {{ background: linear-gradient(180deg, #D9A0A2 0%, #EBC9CA 100%); }}
.pp-fdays {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:.8rem; text-align:center; font-size:.85rem; color:{STEEL}; font-weight:600; }}
.pp-facts {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:.7rem; margin-top:1.1rem; }}
.pp-fact {{ border-radius:12px; padding:.8rem .85rem; background:{PAPER}; }}
.pp-fact .ic {{ width:30px; height:30px; border-radius:50%; display:grid; place-items:center; margin-bottom:.45rem; }}
.pp-fact .k {{ color:{STEEL}; font-size:.8rem; line-height:1.25; }}
.pp-fact .v {{ font-size:1.35rem; font-weight:900; font-variant-numeric: tabular-nums; margin-top:.15rem; }}

/* shelf */
.pp-cols {{ display:grid; grid-template-columns: repeat(5, 1fr); gap:.8rem; align-items:stretch; }}
.pp-col {{ display:flex; flex-direction:column; border-radius:12px; background:{PAPER}; padding:.7rem .7rem .6rem; }}
.pp-col.today {{ background: repeating-linear-gradient(45deg, #FFFFFF, #FFFFFF 6px, #F6F1E4 6px, #F6F1E4 12px); border:1px dashed #D6C9A6; }}
.pp-col.tonight {{ background:#FBEDEE; }}
.pp-units {{ display:flex; flex-wrap:wrap; gap:4px; align-content:flex-end; min-height: 110px; }}
.pp-col .lbl {{ margin-top:.6rem; font-size:.84rem; color:{STEEL}; display:flex; justify-content:space-between; align-items:baseline; gap:.4rem; }}
.pp-col .lbl b {{ color:{INK}; font-size:1.1rem; font-weight:900; font-variant-numeric: tabular-nums; }}
.pp-legend {{ display:flex; gap:1.1rem; margin-top:.9rem; color:{STEEL}; font-size:.84rem; flex-wrap:wrap; align-items:center; }}
.pp-legend span {{ display:inline-flex; align-items:center; gap:.35rem; }}

/* transfers */
.pp-move {{ display:grid; grid-template-columns: auto 1fr auto; align-items:center; gap:.9rem; padding:.85rem .95rem; border-radius:12px; background:{PAPER}; margin-bottom:.55rem; }}
.pp-move .ic {{ width:36px; height:36px; border-radius:10px; display:grid; place-items:center; background:#F7E9EA; }}
.pp-move .route {{ font-weight:700; font-size:.95rem; }}
.pp-move .route span {{ color:{RED}; margin:0 .3rem; }}
.pp-move .meta {{ color:{STEEL}; font-size:.83rem; margin-top:.1rem; }}
.pp-move .q {{ font-weight:900; font-size:1.25rem; font-variant-numeric: tabular-nums; white-space:nowrap; }}
.pp-empty {{ display:flex; gap:.7rem; align-items:flex-start; color:{STEEL}; font-size:.93rem; padding:.85rem .95rem; border-radius:12px; background:{PAPER}; }}
.pp-map svg text {{ font-family: 'Public Sans', sans-serif; }}

/* evaluation */
.pp-caveat {{ display:flex; gap:.7rem; align-items:flex-start; border:1px solid #EDD9A6; padding:.8rem 1rem; background:#FFF9EC; font-size:.92rem; border-radius:12px; margin: .3rem 0 1.1rem; }}
.pp-kpis {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:1.1rem; margin-bottom: 1.1rem; }}
.pp-kpi .ic {{ width:38px; height:38px; border-radius:11px; display:grid; place-items:center; margin-bottom:.7rem; }}
.pp-kpi .k {{ color:{STEEL}; font-size:.9rem; font-weight:600; }}
.pp-kpi .v {{ font-size:2.5rem; font-weight:900; letter-spacing:-0.03em; font-variant-numeric: tabular-nums; line-height:1.1; margin-top:.2rem; }}
.pp-kpi .v .from {{ color:{GREY}; font-weight:800; font-size:1.7rem; }}
.pp-kpi .s {{ color:{STEEL}; font-size:.86rem; margin-top:.35rem; }}
.pp-meter {{ height:8px; border-radius:4px; background:{PAPER}; margin-top:.7rem; overflow:hidden; display:flex; }}
.pp-meter i {{ display:block; height:100%; }}
table.pp-table, table.pp-table th, table.pp-table td, table.pp-table tr {{ border-left:none !important; border-right:none !important; border-top:none !important; }}
table.pp-table {{ border:none !important; width:100%; border-collapse:collapse; font-size:.93rem; font-variant-numeric: tabular-nums; }}
table.pp-table th {{ text-align:right; color:{STEEL}; font-weight:700; padding:.55rem .6rem; border-bottom:1.5px solid {INK}; font-size:.85rem; }}
table.pp-table th:first-child, table.pp-table td:first-child {{ text-align:left; }}
table.pp-table td {{ text-align:right; padding:.6rem .6rem; border-bottom:1px solid {RULE}; }}
table.pp-table tr.ours td {{ font-weight:800; background:#FBEDEE; }}
table.pp-table tr.ours td:first-child {{ color:{RED}; border-radius:8px 0 0 8px; }}
table.pp-table tr.ours td:last-child {{ border-radius:0 8px 8px 0; }}
.pp-p {{ color:{STEEL}; font-size:.92rem; margin:.8rem 0 0; }}

/* keep inputs light even when the visitor's browser is in dark mode */
[data-testid="stSidebar"] .stDateInput div, [data-testid="stSidebar"] .stSelectbox div {{ background-color:{CARD} !important; }}
[data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child:not(:has(input:checked)) {{ background-color:{CARD} !important; }}
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="input"] > div, [data-baseweb="base-input"],
.stDateInput input, .stSelectbox input, input, textarea {{ background:{CARD} !important; color:{INK} !important; -webkit-text-fill-color:{INK} !important; }}
[data-baseweb="select"] > div, [data-baseweb="input"] {{ border:1px solid {RULE} !important; border-radius:10px !important; }}
[data-baseweb="select"] span, [data-baseweb="select"] div {{ color:{INK} !important; }}
[data-baseweb="select"] svg, [data-baseweb="input"] svg {{ fill:{STEEL} !important; }}
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"], [data-baseweb="calendar"], [data-baseweb="calendar"] * {{ background:{CARD} !important; color:{INK} !important; }}
[data-baseweb="calendar"] [aria-selected="true"] div {{ background:{RED} !important; color:#fff !important; }}
[data-testid="stRadio"] label > div:first-child {{ background:{CARD} !important; border:1.5px solid {STEEL} !important; }}
[data-testid="stRadio"] label:has(input:checked) > div:first-child {{ background:{RED} !important; border-color:{RED} !important; }}
[data-testid="stFileUploaderDropzone"] {{ background:{CARD} !important; border:1.5px dashed {GREY} !important; border-radius:14px !important; }}
[data-testid="stFileUploaderDropzone"] * {{ color:{INK} !important; }}
.stButton button, .stDownloadButton button, [data-testid="stBaseButton-secondary"] {{ background:{CARD} !important; color:{INK} !important; border:1px solid {RULE} !important; border-radius:10px !important; font-weight:600 !important; }}
.stButton button:hover, .stDownloadButton button:hover {{ border-color:{RED} !important; color:{RED} !important; }}
[data-testid="stTooltipIcon"] svg {{ stroke:{STEEL} !important; }}
[data-testid="stSidebarCollapseButton"] svg, [data-testid="stExpandSidebarButton"] svg {{ fill:{INK} !important; color:{INK} !important; }}
code {{ color:{RED} !important; background:{PAPER} !important; }}
.pp-side {{ display:flex; align-items:center; gap:.55rem; margin:.2rem 0 .3rem; }}
.pp-side .logo {{ width:34px; height:34px; border-radius:10px; background:{WINE}; display:grid; place-items:center; }}
.pp-side b {{ font-size:1.2rem; font-weight:900; letter-spacing:-0.02em; }}
[data-testid="stVegaLiteChart"] {{ box-sizing:border-box; overflow:hidden; background:{CARD}; border:1px solid {RULE}; border-radius:16px; padding: .9rem 1rem .4rem;
  box-shadow: 0 1px 2px rgba(27,31,39,.04), 0 8px 24px -12px rgba(61,10,16,.18); }}

@media (prefers-reduced-motion: no-preference) {{
  .pp-move.live .ic svg {{ animation: pp-drive 2.4s ease-in-out infinite; }}
  @keyframes pp-drive {{ 0%,100% {{ transform: translateX(-2px); }} 50% {{ transform: translateX(2px); }} }}
}}
@media (max-width: 980px) {{
  .pp-grid, .pp-grid2, .pp-kpis {{ grid-template-columns: 1fr; }}
  .pp-dec {{ grid-template-columns: 1fr; justify-items:start; }}
  .pp-cols {{ grid-template-columns: repeat(2, 1fr); }}
  .pp-chips {{ justify-content:flex-start; }}
}}
</style>
""", unsafe_allow_html=True)


def esc(x):
    return html.escape(str(x))


def day_month(ts):            # "6 Oct" (portable: the %-d format is not supported on Windows)
    return f"{ts.day} {ts.strftime('%b')}"


def long_date(ts):            # "Monday 6 October 2025"
    return f"{ts.strftime('%A')} {ts.day} {ts.strftime('%B %Y')}"


def styled(chart):
    """Apply the PlateletPlan chart style. Charts are drawn with theme=None so Streamlit keeps this style."""
    return (chart.configure(font="Public Sans, Helvetica, Arial, sans-serif", background=CARD)
            .configure_view(stroke=None)
            .configure_axis(labelColor=STEEL, titleColor=STEEL, gridColor=RULE, domainColor=RULE, tickColor=RULE,
                            labelFontSize=12, titleFontSize=12, titleFontWeight=500)
            .configure_legend(labelColor=INK, titleColor=STEEL, labelFontSize=12, orient="top")
            .configure_title(color=INK, fontSize=15, fontWeight=800, anchor="start", offset=12))


@st.cache_resource(show_spinner="Training the forecasts and simulating the district. This takes about 30 seconds the first time.")
def get_system(scenario):
    return build_system(scenario)


# ---------------------------------------------------------------------------
# Sidebar controls (deep links: ?centre=B&date=2025-10-03&scenario=outbreak)
# ---------------------------------------------------------------------------
qp = st.query_params
codes = [c.code for c in C.CENTRES]
q_centre = qp.get("centre", "A") if qp.get("centre", "A") in codes else "A"
try:
    q_date = pd.Timestamp(qp.get("date", "2025-10-06"))
except Exception:
    q_date = pd.Timestamp("2025-10-06")
q_scen = qp.get("scenario", "normal") if qp.get("scenario", "normal") in ("normal", "outbreak") else "normal"

with st.sidebar:
    st.markdown(f'<div class="pp-side"><span class="logo">{icon("drop", 18, "#fff", 2)}</span><b>PlateletPlan</b></div>', unsafe_allow_html=True)
    st.caption("Morning planning for a district's blood centres")
    centre = st.selectbox("Blood centre", codes, index=codes.index(q_centre), format_func=lambda k: CENTRE_LABEL[k])
    date = st.date_input("Date", q_date, min_value=pd.Timestamp("2025-01-01"), max_value=pd.Timestamp("2025-12-29"),
                         help="Any day in the 2025 test year")
    scen_label = st.radio("Dengue season", ["Normal", "Unseen outbreak"], index=0 if q_scen == "normal" else 1,
                          help="Unseen outbreak: the 2025 season is twice as large and peaks three weeks early. The models never saw anything like it.")
    scenario = "normal" if scen_label == "Normal" else "outbreak"
    st.divider()
    st.caption("All centre-level data here is synthetic, generated by a documented script and calibrated to published Indian discard rates. "
               "It shows that the method works, not a measured real-world saving.")

sysm = get_system(scenario)
p = daily_plan(sysm, pd.Timestamp(date), centre)
d = pd.Timestamp(p["date"])

# ---------------------------------------------------------------------------
# Header band
# ---------------------------------------------------------------------------
dengue = sysm.signal.set_index("date")["reported_weekly_cases"]
d_now, d_4w = float(dengue.loc[d]), float(dengue.shift(28).bfill().loc[d])
d_change = (d_now - d_4w) / max(d_4w, 1) * 100
rising = d_change > 15
st.markdown(f"""
<div class="pp-hero"><div class="top">
  <div>
    <div class="brand"><span class="logo">{icon("drop", 24, "#fff", 2)}</span><h1>PlateletPlan</h1></div>
    <div class="tag">Each morning: how many platelet units to prepare, which units are about to expire, and where a nearby centre can use them.</div>
  </div>
  <div class="pp-chips">
    <span class="pp-chip">{icon("map", 16, "#fff")}{esc(CENTRE_LABEL[centre])}</span>
    <span class="pp-chip">{icon("calendar", 16, "#fff")}{long_date(d)}</span>
    <span class="pp-chip {'alert' if rising else ''}">{icon("pulse", 16, "#fff")}Dengue {d_now:.0f} cases/week ({d_change:+.0f}%)</span>
    {'<span class="pp-chip alert">' + icon("alert", 16, "#fff") + 'Unseen outbreak scenario</span>' if scenario == "outbreak" else ''}
  </div>
</div></div>
""", unsafe_allow_html=True)

tab_plan, tab_eval, tab_byo, tab_about = st.tabs(["Today's plan", "How well it works", "Try your own register", "Data and limits"])

# ---------------------------------------------------------------------------
# Today's plan
# ---------------------------------------------------------------------------
with tab_plan:
    # --- decision card ------------------------------------------------------
    H, z = sysm.policy.horizon, sysm.policy.z
    fr = sysm.forecasts[centre].loc[d]
    expected = sum(float(fr[f"f{h}"]) for h in range(H))
    margin = z * sysm.sigma[centre] * (H ** 0.5)
    raw = max(0, math.ceil(expected + margin - p["stock_total"]))
    capped = raw > p["prepare_today"]
    calc = (f'Covers the next {H} day{"s" if H > 1 else ""} (<b>{expected:.0f}</b> units expected) plus a safety margin of '
            f'<b>{margin:.0f}</b>, minus <b>{p["stock_total"]}</b> usable units already in stock'
            + (f'. That needs {raw}, so it is capped at today\'s <b>{p["donations_today"]}</b> donations.' if capped else '.'))

    share = p["prepare_today"] / max(p["donations_today"], 1)
    R, CIRC = 74, 2 * math.pi * 74
    ring = (f'<svg width="170" height="170" viewBox="0 0 170 170" aria-hidden="true">'
            f'<circle cx="85" cy="85" r="{R}" fill="none" stroke="{PAPER}" stroke-width="14"/>'
            f'<circle cx="85" cy="85" r="{R}" fill="none" stroke="{RED}" stroke-width="14" stroke-linecap="round" '
            f'stroke-dasharray="{CIRC * min(share, 1):.1f} {CIRC:.1f}" transform="rotate(-90 85 85)"/></svg>')

    received = sum(m["units"] for m in p["receive"])
    headline = f"Make {p['prepare_today']} platelet units from today's {p['donations_today']} donations"
    if p["prepare_today"] == 0:
        headline = "No new platelet units needed today"
    note = "The ring shows the share of today's donations to process into platelets."
    if received:
        note = f"Includes {received} near-expiry unit{'s' if received != 1 else ''} arriving from a nearby centre. " + note

    reason_rows = ""
    if p["reason"] == "close to a normal day":
        reason_rows = '<div class="pp-reason"><div>Close to a normal day: nothing unusual is pushing demand up or down</div><div></div></div>'
    else:
        def as_num(v):  # reason values use a typographic minus sign
            return float(v.replace("\u2212", "-"))
        parts = [part.rsplit(" ", 1) for part in p["reason"].split("; ")]
        biggest = max(abs(as_num(v)) for _, v in parts) or 1
        for label, val in parts:
            cls = "up" if as_num(val) >= 0 else "down"
            width = abs(as_num(val)) / biggest * 100
            reason_rows += (f'<div class="pp-reason"><div>{esc(label[0].upper() + label[1:])}'
                            f'<div class="bar {cls}" style="width:{width:.0f}%"></div></div>'
                            f'<div class="v {cls}">{esc(val)} units</div></div>')

    # --- forecast + facts card ----------------------------------------------
    fvals = list(p["forecast"].items())
    top = max(v for _, v in fvals) or 1
    fbars, fdays = "", ""
    for i, (day, val) in enumerate(fvals):
        dd = pd.Timestamp(day)
        fbars += (f'<div class="pp-fbar {"later" if i else ""}"><div class="val">{val:.0f}</div>'
                  f'<div class="col" style="height:{max(val / top * 100, 6):.0f}px"></div></div>')
        name = "Today" if i == 0 else ("Tomorrow" if i == 1 else dd.strftime("%A"))
        fdays += f'<div>{name}<br><span style="font-weight:500">{day_month(dd)}</span></div>'

    expiring_tonight = p["stock_by_age"]["1 day(s) left"]
    facts = [
        ("stack", "#EAF0F6", SKY, "Usable stock this morning", f'{p["stock_total"]}'),
        ("clock", "#FBEDEE", RED, "Expire tonight if unused", f"{expiring_tonight}"),
        ("pulse", "#FFF4DD", AMBER, "District dengue cases, last week", f"{p['dengue_reported_weekly']}"),
    ]
    facts_html = "".join(f'<div class="pp-fact"><div class="ic" style="background:{bg}">{icon(ic, 17, col, 2)}</div>'
                         f'<div class="k">{k}</div><div class="v">{v}</div></div>' for ic, bg, col, k, v in facts)

    st.markdown(f"""
<div class="pp-grid">
  <div class="pp-card">
    <div class="pp-h"><span class="ic">{icon("drop", 17)}</span>Today's decision<span class="sub">{esc(CENTRE_LABEL[centre])}</span></div>
    <div class="pp-dec">
      <div class="pp-ring">{ring}<div class="c"><div class="n">{p['prepare_today']}</div><div class="u">units to prepare</div></div></div>
      <div>
        <div class="pp-verb">Prepare today</div>
        <div class="pp-headline">{esc(headline)}</div>
        <div class="pp-note">{esc(note)}</div>
      </div>
    </div>
    <div class="pp-calc">{calc}</div>
    <div class="pp-why"><div class="t">What moved the forecast today</div>{reason_rows}</div>
  </div>
  <div class="pp-card">
    <div class="pp-h"><span class="ic">{icon("chart", 17)}</span>Expected demand<span class="sub">units per day</span></div>
    <div class="pp-fbars">{fbars}</div>
    <div class="pp-fdays">{fdays}</div>
    <div class="pp-facts">{facts_html}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # --- the platelet shelf ---------------------------------------------------
    cols = ""
    for days_left in range(5, 0, -1):
        n = p["stock_by_age"][f"{days_left} day(s) left"]
        new = p["prepare_today"] if days_left == 5 else 0
        shown = min(n, 48)
        units = "".join(bag(LIFE_COLOURS[days_left]) for _ in range(shown))
        units += "".join(bag(INK, new=True) for _ in range(min(new, 40)))
        more = f'<span style="font-size:.8rem;color:{STEEL};align-self:center">+{n - shown}</span>' if n > shown else ""
        label = "Fresh today" if days_left == 5 else ("Expires tonight" if days_left == 1 else f"{days_left} days left")
        count = f"{n + new}" if days_left == 5 else f"{n}"
        cls = "today" if days_left == 5 else ("tonight" if days_left == 1 else "")
        cols += f'<div class="pp-col {cls}"><div class="pp-units">{units}{more}</div><div class="lbl"><span>{label}</span><b>{count}</b></div></div>'
    legend = "".join(f'<span>{bag(LIFE_COLOURS[k], w=11, h=16)}{k} day{"s" if k > 1 else ""} left</span>' for k in range(5, 0, -1))
    legend += f'<span>{bag(INK, new=True, w=11, h=16)}To prepare today</span>'

    st.markdown(f"""
<div class="pp-card">
  <div class="pp-h"><span class="ic">{icon("stack", 17)}</span>Platelet shelf<span class="sub">every unit on the agitator, by days of life left</span></div>
  <div class="pp-cols">{cols}</div>
  <div class="pp-legend">{legend}</div>
</div>
""", unsafe_allow_html=True)

    # --- district map + transfers ----------------------------------------------
    day_rec = sysm.records[sysm.records["date"] == d].set_index("centre")
    W, Hh = 560, 310
    # schematic layout (roughly geographic, spread out so labels never collide)
    LAYOUT = {"A": (180, 130), "B": (330, 80), "C": (470, 185), "D": (80, 230), "E": (310, 250)}

    def xy(c):
        return LAYOUT.get(c.code, (W / 2, Hh / 2))

    pos = {c.code: xy(c) for c in C.CENTRES}
    moves_today = sysm.moves[pd.to_datetime(sysm.moves["date"]) == d]
    svg = [f'<svg viewBox="0 0 {W} {Hh}" width="100%" role="img" aria-label="District map of blood centres and today\'s transfers">',
           f'<defs><pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="{RULE}"/></pattern>'
           f'<marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           f'<path d="M0 0 L10 5 L0 10 z" fill="{RED}"/></marker></defs>',
           f'<rect width="{W}" height="{Hh}" rx="12" fill="url(#dots)"/>']
    # road links (within transfer range)
    tv = travel_minutes()
    for _, r in tv.iterrows():
        if r["from"] < r["to"] and r["minutes"] <= C.MAX_TRANSFER_MINUTES:
            (x1, y1), (x2, y2) = pos[r["from"]], pos[r["to"]]
            svg.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#C9CED6" stroke-width="1.3" stroke-dasharray="2 5" stroke-linecap="round"/>')
    # today's transfers
    for _, m in moves_today.iterrows():
        (x1, y1), (x2, y2) = pos[m["from"]], pos[m["to"]]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        sx, sy, ex, ey = x1 + ux * 30, y1 + uy * 30, x2 - ux * 34, y2 - uy * 34
        mx, my = (sx + ex) / 2 - uy * 26, (sy + ey) / 2 + ux * 26          # curve control point
        svg.append(f'<path d="M{sx:.0f} {sy:.0f} Q{mx:.0f} {my:.0f} {ex:.0f} {ey:.0f}" fill="none" stroke="{RED}" stroke-width="3" marker-end="url(#arr)"/>')
        lx = 0.25 * sx + 0.5 * mx + 0.25 * ex - uy * 16                      # label just outside the curve
        ly = 0.25 * sy + 0.5 * my + 0.25 * ey + ux * 16
        txt = f'{int(m["units"])} units · {int(m["minutes"])} min'
        pw = len(txt) * 6.4 + 18
        svg.append(f'<rect x="{lx - pw / 2:.0f}" y="{ly - 11:.0f}" width="{pw:.0f}" height="22" rx="11" fill="{RED}"/>'
                   f'<text x="{lx:.0f}" y="{ly + 4:.0f}" font-size="11" font-weight="800" fill="#fff" text-anchor="middle">{txt}</text>')
    # centres
    for c in C.CENTRES:
        x, y = pos[c.code]
        r = day_rec.loc[c.code]
        stock = int(sum(r[f"age{a}"] for a in range(C.SHELF_LIFE_DAYS)))
        risk = int(r[f"age{C.SHELF_LIFE_DAYS - 1}"] + r[f"age{C.SHELF_LIFE_DAYS - 2}"])
        rad = 16 + math.sqrt(stock) * 1.6
        sel = c.code == centre
        frac = risk / stock if stock else 0
        fill = RED if frac > .35 else (ORANGE if frac > .2 else STRAW)
        svg.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad + 6:.0f}" fill="{fill}" opacity=".16"/>')
        svg.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad:.0f}" fill="#fff" stroke="{INK if sel else fill}" stroke-width="{3.5 if sel else 2.5}"/>')
        svg.append(f'<text x="{x:.0f}" y="{y + 5:.0f}" font-size="15" font-weight="900" fill="{INK}" text-anchor="middle">{c.code}</text>')
        above = y < 100                                  # top-row centres get their label above the circle
        ly = (y - rad - 22) if above else (y + rad + 17)
        svg.append(f'<text x="{x:.0f}" y="{ly:.0f}" font-size="12" font-weight="{800 if sel else 600}" fill="{INK}" text-anchor="middle">{esc(CENTRE_NAMES[c.code])}</text>')
        svg.append(f'<text x="{x:.0f}" y="{ly + 14:.0f}" font-size="11" fill="{STEEL}" text-anchor="middle">{stock} units · {risk} expiring soon</text>')
    svg.append("</svg>")

    moves_html = ""
    for m in p["send"]:
        moves_html += (f'<div class="pp-move live"><div class="ic">{icon("truck", 20, RED)}</div><div><div class="route">This centre<span>→</span>{esc(m["to"].split(" - ")[1])}</div>'
                       f'<div class="meta">Send the oldest units · about {m["minutes"]} min by road</div></div><div class="q">−{m["units"]}</div></div>')
    for m in p["receive"]:
        moves_html += (f'<div class="pp-move live"><div class="ic">{icon("truck", 20, RED)}</div><div><div class="route">{esc(m["from"].split(" - ")[1])}<span>→</span>this centre</div>'
                       f'<div class="meta">Near-expiry units, used before any fresh ones · about {m["minutes"]} min</div></div><div class="q">+{m["units"]}</div></div>')
    if not moves_html:
        moves_html = (f'<div class="pp-empty">{icon("check", 20, GOOD, 2.2)}<div>No transfers for this centre today. '
                      f'It has no spare units that will expire before use, and it is not short.</div></div>')
    others = len(moves_today) - len(p["send"]) - len(p["receive"])
    if others > 0:
        moves_html += f'<p class="pp-p">{others} other transfer{"s" if others > 1 else ""} between centres in the district today are shown on the map.</p>'

    st.markdown(f"""
<div class="pp-grid2">
  <div class="pp-card pp-map">
    <div class="pp-h"><span class="ic">{icon("map", 17)}</span>District network<span class="sub">size = stock · ring = share expiring soon</span></div>
    {''.join(svg)}
  </div>
  <div class="pp-card">
    <div class="pp-h"><span class="ic">{icon("truck", 17)}</span>Transfers today</div>
    {moves_html}
  </div>
</div>
""", unsafe_allow_html=True)

    # --- history chart ---------------------------------------------------------
    rec = sysm.records[sysm.records["centre"] == centre].set_index("date")
    f0 = sysm.forecasts[centre]["f0"]
    win = rec.loc[d - pd.Timedelta(days=60):d]
    dfc = pd.DataFrame({"date": win.index, "Units issued": win["demand"].values, "Morning forecast": f0.loc[win.index].values})
    base = alt.Chart(dfc).encode(x=alt.X("date:T", title=None))
    bars = base.mark_bar(color="#E6C9CA", cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        y=alt.Y("Units issued:Q", title="units per day"), tooltip=[alt.Tooltip("date:T"), "Units issued:Q"])
    fl = base.mark_line(color=RED, strokeWidth=2.5).encode(y="Morning forecast:Q",
                                                           tooltip=[alt.Tooltip("date:T"), alt.Tooltip("Morning forecast:Q", format=".1f")])
    st.altair_chart(styled((bars + fl).properties(height=250, title="Last 60 days: units issued (bars) and the forecast made each morning (line)")),
                    width="stretch", theme=None)
    st.caption(f"Units actually issued on {day_month(d)} (known only at the end of the day): {p['actual_demand']}.")

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def load_eval(name):
    f = RES / name
    return pd.read_csv(f) if f.exists() else None


SHORT = {"Status quo (fixed share of donations)": "Status quo", "7-day average baseline": "7-day average",
         "PlateletPlan (LASSO forecast)": "PlateletPlan", "PlateletPlan + transfers": "PlateletPlan + transfers"}


def eval_table(ev):
    rows = ""
    for _, r in ev.iterrows():
        ours = "ours" if r["policy"] == "PlateletPlan + transfers" else ""
        rows += (f'<tr class="{ours}"><td>{esc(SHORT[r["policy"]])}</td><td>{int(r["units_prepared"]):,}</td><td>{int(r["units_expired"]):,}</td>'
                 f'<td>{r["expiry_rate"] * 100:.1f}%</td><td>{int(r["units_short"]):,}</td><td>{r["shortage_rate"] * 100:.2f}%</td><td>{int(r["units_transferred"]):,}</td></tr>')
    return ('<table class="pp-table"><tr><th>Policy</th><th>Prepared</th><th>Expired</th><th>Expiry rate</th>'
            f'<th>Short</th><th>Shortage rate</th><th>Transferred</th></tr>{rows}</table>')


with tab_eval:
    ev, ev_s, summ = load_eval("evaluation_test_year.csv"), load_eval("stress_evaluation_test_year.csv"), load_eval("summary_across_seeds.csv")
    if ev is None:
        st.warning("Result files are missing. Run `python pp_pipeline.py` to create them.")
    else:
        sq, ours, base_r = ev.iloc[0], ev.iloc[3], ev.iloc[1]
        saved = int(sq["units_expired"] - ours["units_expired"])
        st.markdown(f"""
<div class="pp-caveat">{icon("alert", 20, AMBER, 2)}<div>In simulation, on a synthetic district of five centres. The models were fitted on 2021–23, tuned on 2024 and tested on 2025, which they never saw.
These results show the method is worth testing on real registers. They are not a measured real-world saving.</div></div>
<div class="pp-kpis">
  <div class="pp-card pp-kpi"><div class="ic" style="background:#FBEDEE">{icon("clock", 20, RED, 2)}</div>
    <div class="k">Platelets expired</div><div class="v"><span class="from">{sq['expiry_rate'] * 100:.1f}% →</span> {ours['expiry_rate'] * 100:.1f}%</div>
    <div class="s">status quo vs PlateletPlan with transfers</div>
    <div class="pp-meter"><i style="width:{ours['expiry_rate'] * 100:.1f}%;background:{RED}"></i><i style="width:{(sq['expiry_rate'] - ours['expiry_rate']) * 100:.1f}%;background:#E6C9CA"></i></div></div>
  <div class="pp-card pp-kpi"><div class="ic" style="background:#EAF3EE">{icon("check", 20, GOOD, 2.2)}</div>
    <div class="k">Units saved from expiry in 2025</div><div class="v">{saved:,}</div>
    <div class="s">across the five centres, each one a donation used instead of discarded</div></div>
  <div class="pp-card pp-kpi"><div class="ic" style="background:#EAF0F6">{icon("truck", 20, SKY, 2)}</div>
    <div class="k">Units short vs a simple forecast</div><div class="v"><span class="from">{int(base_r['units_short'])} →</span> {int(ours['units_short'])}</div>
    <div class="s">7-day average vs PlateletPlan with transfers</div></div>
</div>
""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        bars_df = ev.assign(name=ev["policy"].map(SHORT), pct=ev["expiry_rate"] * 100)
        dom, rng = list(SHORT.values()), [GREY, GREY, STRAW, RED]
        ch = alt.Chart(bars_df).mark_bar(cornerRadiusEnd=5, height=28).encode(
            y=alt.Y("name:N", sort=dom, title=None), x=alt.X("pct:Q", title="% of prepared units that expired", scale=alt.Scale(domain=[0, float(bars_df["pct"].max()) * 1.15])),
            color=alt.Color("name:N", scale=alt.Scale(domain=dom, range=rng), legend=None),
            tooltip=[alt.Tooltip("name:N", title="Policy"), alt.Tooltip("pct:Q", format=".1f", title="Expiry %")])
        c1.altair_chart(styled((ch + ch.mark_text(align="left", dx=6, color=INK, fontWeight=800).encode(text=alt.Text("pct:Q", format=".1f")))
                               .properties(height=230, title="Expiry rate, test year 2025")), width="stretch", theme=None)
        sh = alt.Chart(bars_df).mark_bar(cornerRadiusEnd=5, height=28).encode(
            y=alt.Y("name:N", sort=dom, title=None), x=alt.X("units_short:Q", title="units of demand not met", scale=alt.Scale(domain=[0, max(float(bars_df["units_short"].max()) * 1.18, 1)])),
            color=alt.Color("name:N", scale=alt.Scale(domain=dom, range=rng), legend=None),
            tooltip=[alt.Tooltip("name:N", title="Policy"), alt.Tooltip("units_short:Q", title="Units short")])
        c2.altair_chart(styled((sh + sh.mark_text(align="left", dx=6, color=INK, fontWeight=800).encode(text="units_short:Q"))
                               .properties(height=230, title="Units short, test year 2025")), width="stretch", theme=None)

        st.markdown(f'<div class="pp-card" style="margin-top:1.1rem"><div class="pp-h"><span class="ic">{icon("chart", 17)}</span>Normal season, 2025</div>{eval_table(ev)}</div>',
                    unsafe_allow_html=True)
        if ev_s is not None:
            st.markdown(f'<div class="pp-card" style="margin-top:1.1rem"><div class="pp-h"><span class="ic">{icon("alert", 17)}</span>Unseen outbreak: 2025 season twice as large and three weeks early</div>'
                        f'{eval_table(ev_s)}<p class="pp-p">Transfers halve shortages compared with the 7-day average. The status quo holds so much extra stock that it '
                        f'runs short slightly less often, but it throws away about 7,000 more units. An outbreak mode that raises safety stock when cases climb is the next step.</p></div>',
                        unsafe_allow_html=True)
        st.markdown("")
        mon = load_eval("evaluation_by_month.csv")
        if mon is not None:
            mon = mon.assign(name=mon["policy"].map(SHORT), pct=mon["expired"] / mon["prepared"].clip(lower=1) * 100, m=pd.to_datetime(mon["month"]))
            lc = alt.Chart(mon).mark_line(point=True, strokeWidth=2.5).encode(
                x=alt.X("m:T", title=None, axis=alt.Axis(format="%b")), y=alt.Y("pct:Q", title="% expired"),
                color=alt.Color("name:N", scale=alt.Scale(domain=dom, range=[GREY, "#6E7785", STRAW, RED]), title=None),
                tooltip=["name:N", alt.Tooltip("m:T", format="%B"), alt.Tooltip("pct:Q", format=".1f")])
            st.altair_chart(styled(lc.properties(height=260, title="Expiry rate by month, 2025")), width="stretch", theme=None)
        if summ is not None:
            s = summ.set_index("policy")
            st.markdown(f'<p class="pp-p">Across three random seeds (7, 21, 42), PlateletPlan with transfers averages '
                        f'{s.loc["PlateletPlan + transfers", "expiry_rate_mean"] * 100:.1f}% expiry, against '
                        f'{s.loc["Status quo (fixed share of donations)", "expiry_rate_mean"] * 100:.1f}% for the status quo and '
                        f'{s.loc["7-day average baseline", "expiry_rate_mean"] * 100:.1f}% for the 7-day average.</p>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Bring your own register
# ---------------------------------------------------------------------------
with tab_byo:
    st.markdown(f"""<div class="pp-card"><div class="pp-h"><span class="ic">{icon("stack", 17)}</span>Test PlateletPlan on a real centre's register</div>
<p style="margin:0">Upload one blood centre's daily register as a CSV with the columns <b>date</b> and <b>issued</b> (platelet units issued that day),
and optionally <b>dengue_cases</b> (district cases per day). At least 120 days are needed. PlateletPlan learns from the first 70% of days,
then replays the rest and compares itself with a 7-day average.</p></div>""", unsafe_allow_html=True)
    st.markdown("")
    sample = ROOT / "sample_register.csv"
    c1, c2 = st.columns([1, 2])
    if sample.exists():
        c1.download_button("Download a sample register", sample.read_bytes(), "sample_register.csv", width="stretch")
    up = c2.file_uploader("Register CSV", type="csv", label_visibility="collapsed")
    if up is not None:
        try:
            out = plan_from_register(pd.read_csv(up))
            bt = out["backtest"]
            rows = ""
            for name, r in bt.items():
                cls = "ours" if name == "PlateletPlan" else ""
                rows += (f'<tr class="{cls}"><td>{esc(name)}</td><td>{r["units_prepared"]:,}</td><td>{r["units_expired"]:,}</td>'
                         f'<td>{r["expiry_rate"] * 100:.1f}%</td><td>{r["units_short"]:,}</td><td>{r["shortage_rate"] * 100:.2f}%</td><td>{r["wape"]:.2f}</td></tr>')
            t = out["tomorrow"]
            st.markdown(f"""<div class="pp-card"><div class="pp-h"><span class="ic">{icon("chart", 17)}</span>Replay of the last {out['test_days']} days</div>
<table class="pp-table"><tr><th>Policy</th><th>Prepared</th><th>Expired</th><th>Expiry rate</th><th>Short</th><th>Shortage rate</th><th>Forecast error</th></tr>{rows}</table>
<div class="pp-why"><div class="t">Plan for {long_date(pd.Timestamp(t['date']))}</div>
<div class="pp-reason"><div>Expected demand over the next three days</div><div class="v">{t['forecast'][0]} · {t['forecast'][1]} · {t['forecast'][2]} units</div></div>
<div class="pp-reason"><div>Keep this much usable stock</div><div class="v">{t['target_stock']} units</div></div>
<div class="pp-reason"><div>So prepare</div><div class="v">{t['target_stock']} minus usable units on hand, up to the donations available</div></div>
</div></div>""", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Could not read this register: {e}")

# ---------------------------------------------------------------------------
# Data and limits
# ---------------------------------------------------------------------------
with tab_about:
    doc = ROOT / "DATA.md"
    st.markdown(doc.read_text() if doc.exists() else "See DATA.md in the repository.")
