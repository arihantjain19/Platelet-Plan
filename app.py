"""PlateletPlan - Streamlit app.  Run:  streamlit run app.py"""
import html
import pathlib

import altair as alt
import pandas as pd
import streamlit as st

import pp_config as C
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
INK, STEEL, RULE, PAPER, CARD = "#1B1F27", "#5C6573", "#E2E5EA", "#F6F7F9", "#FFFFFF"
RED, STRAW, AMBER, ORANGE = "#A4161A", "#E3A73B", "#D98A2B", "#C4521F"
GOOD, GREY = "#2F6B4F", "#A9B0BA"
LIFE_COLOURS = {5: "#EDC261", 4: STRAW, 3: AMBER, 2: ORANGE, 1: RED}  # days of life left
CENTRE_NAMES = {c.code: c.name.split(" - ")[1] for c in C.CENTRES}
CENTRE_LABEL = {c.code: f"Centre {c.code} · {c.name.split(' - ')[1]}" for c in C.CENTRES}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800&display=swap');
html, body, .stApp, [class*="css"], .stMarkdown, button, input, select, textarea {{ font-family: 'Public Sans', sans-serif !important; }}
.stApp {{ background: {PAPER}; color: {INK}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {RULE}; }}
[data-testid="stSidebar"] * {{ color: {INK}; }}
.block-container {{ padding-top: 2.2rem; max-width: 1240px; }}
h1, h2, h3, h4, p, li, label, span, div {{ color: {INK}; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid {RULE}; }}
.stTabs [data-baseweb="tab"] {{ padding: 0.6rem 0; font-weight: 600; color: {STEEL}; background: transparent; }}
.stTabs [aria-selected="true"] {{ color: {INK}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {RED}; }}
.num {{ font-variant-numeric: tabular-nums; }}

.pp-brand {{ display:flex; align-items:baseline; gap:.6rem; margin-bottom:.2rem; }}
.pp-brand .mark {{ font-size: 1.55rem; font-weight: 800; letter-spacing: -0.02em; }}
.pp-brand .drop {{ width:.75rem; height:.75rem; background:{RED}; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); display:inline-block; }}
.pp-sub {{ color:{STEEL}; font-size:.95rem; margin-bottom:1.2rem; max-width: 70ch; }}

.pp-panel {{ background:{CARD}; border:1px solid {RULE}; border-radius:14px; padding:1.4rem 1.6rem; }}
.pp-decision {{ display:grid; grid-template-columns: 1.15fr 1fr; gap: 2rem; align-items: start; }}
.pp-where {{ color:{STEEL}; font-size:.95rem; margin-bottom:.6rem; }}
.pp-big {{ font-size: 4.6rem; font-weight: 800; line-height: .95; letter-spacing:-0.03em; color:{INK}; }}
.pp-big small {{ font-size: 1.35rem; font-weight: 600; letter-spacing: 0; margin-left:.35rem; color:{INK}; }}
.pp-verb {{ font-size: 1.05rem; font-weight: 600; color:{RED}; margin-bottom:.35rem; }}
.pp-note {{ color:{STEEL}; margin-top:.55rem; font-size:.95rem; }}
.pp-why {{ margin-top: 1.1rem; border-top:1px solid {RULE}; padding-top:.9rem; }}
.pp-why h4, .pp-fc h4, .pp-shelf h4, .pp-moves h4 {{ font-size:.95rem; font-weight:700; margin:0 0 .55rem 0; }}
.pp-reason {{ display:flex; justify-content:space-between; gap:1rem; padding:.32rem 0; border-bottom:1px dashed {RULE}; font-size:.95rem; }}
.pp-reason:last-child {{ border-bottom:none; }}
.pp-reason .v {{ font-weight:700; font-variant-numeric: tabular-nums; white-space:nowrap; }}
.pp-reason .up {{ color:{RED}; }} .pp-reason .down {{ color:{GOOD}; }}

.pp-fc {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:.7rem; }}
.pp-day {{ border:1px solid {RULE}; border-radius:10px; padding:.75rem .85rem; }}
.pp-day.today {{ border-color:{INK}; }}
.pp-day .d {{ color:{STEEL}; font-size:.85rem; }}
.pp-day .n {{ font-size:1.9rem; font-weight:800; font-variant-numeric: tabular-nums; }}
.pp-day .u {{ color:{STEEL}; font-size:.85rem; }}
.pp-facts {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:.7rem; margin-top:.9rem; }}
.pp-fact .k {{ color:{STEEL}; font-size:.82rem; }}
.pp-fact .v {{ font-size:1.15rem; font-weight:700; font-variant-numeric: tabular-nums; }}

.pp-shelf {{ margin-top: 1.2rem; }}
.pp-cols {{ display:grid; grid-template-columns: repeat(5, 1fr); gap:.9rem; align-items:end; }}
.pp-col {{ display:flex; flex-direction:column; }}
.pp-units {{ display:flex; flex-wrap:wrap-reverse; gap:4px; min-height: 92px; align-content:flex-start; padding:.5rem; background:{PAPER}; border-radius:8px; }}
.pp-unit {{ width:14px; height:20px; border-radius:3px 3px 5px 5px; }}
.pp-unit.new {{ background: transparent !important; border:2px dashed {INK}; }}
.pp-col .lbl {{ margin-top:.45rem; font-size:.85rem; color:{STEEL}; display:flex; justify-content:space-between; }}
.pp-col .lbl b {{ color:{INK}; font-variant-numeric: tabular-nums; }}
.pp-legend {{ display:flex; gap:1.2rem; margin-top:.8rem; color:{STEEL}; font-size:.85rem; flex-wrap:wrap; }}
.pp-legend span {{ display:inline-flex; align-items:center; gap:.4rem; }}
.pp-legend i {{ display:inline-block; width:10px; height:14px; border-radius:2px 2px 4px 4px; }}

.pp-moves {{ margin-top:1.2rem; }}
.pp-move {{ display:grid; grid-template-columns: 1fr auto 1fr auto; align-items:center; gap:.9rem; padding:.75rem .9rem; border:1px solid {RULE}; border-radius:10px; margin-bottom:.5rem; }}
.pp-move .c {{ font-weight:600; }}
.pp-move .arrow {{ color:{RED}; font-weight:800; }}
.pp-move .q {{ font-weight:800; font-variant-numeric: tabular-nums; white-space:nowrap; }}
.pp-empty {{ color:{STEEL}; font-size:.95rem; }}

.pp-kpis {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:1rem; }}
.pp-kpi .k {{ color:{STEEL}; font-size:.9rem; }}
.pp-kpi .v {{ font-size:2.3rem; font-weight:800; letter-spacing:-0.02em; font-variant-numeric: tabular-nums; }}
.pp-kpi .v .from {{ color:{GREY}; font-weight:700; }}
.pp-kpi .s {{ color:{STEEL}; font-size:.88rem; }}
.pp-caveat {{ border-left:3px solid {STRAW}; padding:.6rem .9rem; background:{CARD}; color:{INK}; font-size:.92rem; border-radius:0 8px 8px 0; margin: .8rem 0 1.2rem; }}
table.pp-table {{ width:100%; border-collapse:collapse; font-size:.93rem; font-variant-numeric: tabular-nums; }}
table.pp-table th {{ text-align:right; color:{STEEL}; font-weight:600; padding:.45rem .6rem; border-bottom:1px solid {INK}; }}
table.pp-table th:first-child, table.pp-table td:first-child {{ text-align:left; }}
table.pp-table td {{ text-align:right; padding:.5rem .6rem; border-bottom:1px solid {RULE}; }}
table.pp-table tr.ours td {{ font-weight:700; }}
table.pp-table tr.ours td:first-child {{ color:{RED}; }}

/* keep inputs light even when the visitor's browser is in dark mode */
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="input"] > div, [data-baseweb="base-input"],
.stDateInput input, .stSelectbox input, input, textarea {{ background:{CARD} !important; color:{INK} !important; -webkit-text-fill-color:{INK} !important; }}
[data-baseweb="select"] > div, [data-baseweb="input"] {{ border:1px solid {RULE} !important; border-radius:8px !important; }}
[data-baseweb="select"] span, [data-baseweb="select"] div {{ color:{INK} !important; }}
[data-baseweb="select"] svg, [data-baseweb="input"] svg {{ fill:{STEEL} !important; }}
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"], [data-baseweb="calendar"], [data-baseweb="calendar"] * {{ background:{CARD} !important; color:{INK} !important; }}
[data-baseweb="calendar"] [aria-selected="true"] div {{ background:{RED} !important; color:#fff !important; }}
[data-testid="stRadio"] label > div:first-child {{ background:{CARD} !important; border:1.5px solid {STEEL} !important; }}
[data-testid="stRadio"] label:has(input:checked) > div:first-child {{ background:{RED} !important; border-color:{RED} !important; }}
[data-testid="stFileUploaderDropzone"] {{ background:{CARD} !important; border:1px dashed {STEEL} !important; }}
[data-testid="stFileUploaderDropzone"] * {{ color:{INK} !important; }}
.stButton button, .stDownloadButton button, [data-testid="stBaseButton-secondary"] {{ background:{CARD} !important; color:{INK} !important; border:1px solid {RULE} !important; }}
.stButton button:hover, .stDownloadButton button:hover {{ border-color:{RED} !important; color:{RED} !important; }}
[data-testid="stTooltipIcon"] svg {{ stroke:{STEEL} !important; }}
[data-testid="stSidebarCollapseButton"] svg, [data-testid="stExpandSidebarButton"] svg {{ fill:{INK} !important; color:{INK} !important; }}
code {{ color:{RED} !important; background:{PAPER} !important; }}
.pp-calc {{ margin-top:.45rem; font-size:.92rem; color:{STEEL}; }}
.pp-calc b {{ color:{INK}; font-variant-numeric: tabular-nums; }}

@media (max-width: 900px) {{
  .pp-decision {{ grid-template-columns: 1fr; }}
  .pp-big {{ font-size: 3.4rem; }}
  .pp-cols {{ gap:.4rem; }}
  .pp-kpis {{ grid-template-columns: 1fr; }}
  .pp-move {{ grid-template-columns: 1fr auto; }}
}}
</style>
""", unsafe_allow_html=True)


def esc(x):
    return html.escape(str(x))


def day_month(ts):            # "6 Oct" (portable: %-d is not supported on Windows)
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
            .configure_title(color=INK, fontSize=14, fontWeight=700, anchor="start"))


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
    st.markdown('<div class="pp-brand"><span class="drop"></span><span class="mark">PlateletPlan</span></div>', unsafe_allow_html=True)
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

st.markdown('<div class="pp-sub">Every morning PlateletPlan tells a blood centre how many platelet units to prepare, '
            'which units are about to expire and where a nearby centre can use them.</div>', unsafe_allow_html=True)

tab_plan, tab_eval, tab_byo, tab_about = st.tabs(["Today's plan", "How well it works", "Try your own register", "Data and limits"])

# ---------------------------------------------------------------------------
# Today's plan
# ---------------------------------------------------------------------------
with tab_plan:
    sysm = get_system(scenario)
    p = daily_plan(sysm, pd.Timestamp(date), centre)
    d = pd.Timestamp(p["date"])

    # reasons: "Monday +1.3; dengue cases 45/week (+18% vs 4 weeks ago) +1.2"
    reason_rows = ""
    if p["reason"] == "close to a normal day":
        reason_rows = '<div class="pp-reason"><span>Nothing unusual today: close to a normal day</span></div>'
    else:
        for part in p["reason"].split("; "):
            label, val = part.rsplit(" ", 1)
            cls = "up" if val.startswith("+") else "down"
            reason_rows += f'<div class="pp-reason"><span>{esc(label[0].upper() + label[1:])}</span><span class="v {cls}">{esc(val)} units</span></div>'

    fc_cards = ""
    for i, (day, val) in enumerate(p["forecast"].items()):
        dd = pd.Timestamp(day)
        name = "Today" if i == 0 else ("Tomorrow" if i == 1 else dd.strftime("%A"))
        fc_cards += (f'<div class="pp-day {"today" if i == 0 else ""}"><div class="d">{name}, {day_month(dd)}</div>'
                     f'<div class="n">{val:.0f}</div><div class="u">units expected</div></div>')

    expiring_tonight = p["stock_by_age"]["1 day(s) left"]
    H, z = sysm.policy.horizon, sysm.policy.z
    fr = sysm.forecasts[centre].loc[d]
    expected = sum(float(fr[f"f{h}"]) for h in range(H))
    margin = z * sysm.sigma[centre] * (H ** 0.5)
    raw = max(0, int(-(-(expected + margin - p["stock_total"]) // 1)))
    capped = raw > p["prepare_today"]
    calc = (f'Covers the next {H} day{"s" if H > 1 else ""} (<b>{expected:.0f}</b> units expected) plus a safety margin of '
            f'<b>{margin:.0f}</b>, minus <b>{p["stock_total"]}</b> usable units in stock'
            + (f'. That needs {raw}, so it is capped at today\'s <b>{p["donations_today"]}</b> donations.' if capped else '.'))
    received = sum(m["units"] for m in p["receive"])
    note = f"from {p['donations_today']} whole-blood donations today"
    if received:
        note += f", after receiving {received} unit{'s' if received != 1 else ''} from a nearby centre"

    st.markdown(f"""
<div class="pp-panel">
  <div class="pp-where">{esc(CENTRE_LABEL[centre])} · {long_date(d)}{' · unseen outbreak scenario' if scenario == 'outbreak' else ''}</div>
  <div class="pp-decision">
    <div>
      <div class="pp-verb">Prepare today</div>
      <div class="pp-big num">{p['prepare_today']}<small>platelet units</small></div>
      <div class="pp-note">{esc(note)}</div>
      <div class="pp-calc">{calc}</div>
      <div class="pp-why"><h4>Why this number</h4>{reason_rows}</div>
    </div>
    <div>
      <div class="pp-fc">{fc_cards}</div>
      <div class="pp-facts">
        <div class="pp-fact"><div class="k">Usable stock this morning</div><div class="v">{p['stock_total']} units</div></div>
        <div class="pp-fact"><div class="k">Expire tonight if unused</div><div class="v" style="color:{RED if expiring_tonight else INK}">{expiring_tonight} units</div></div>
        <div class="pp-fact"><div class="k">District dengue, last week</div><div class="v">{p['dengue_reported_weekly']} cases</div></div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # --- the platelet shelf ---------------------------------------------------
    cols = ""
    for days_left in range(5, 0, -1):
        n = p["stock_by_age"][f"{days_left} day(s) left"]
        new = p["prepare_today"] if days_left == 5 else 0
        shown = min(n, 60)
        units = "".join(f'<span class="pp-unit" style="background:{LIFE_COLOURS[days_left]}"></span>' for _ in range(shown))
        units += "".join('<span class="pp-unit new"></span>' for _ in range(min(new, 40)))
        extra = f" (+{n - shown} more)" if n > shown else ""
        label = "Prepared today" if days_left == 5 else ("Expires tonight" if days_left == 1 else f"{days_left} days left")
        count = f"{n} + {new} new" if days_left == 5 and n else (f"{new} new" if days_left == 5 else f"{n}{extra}")
        cols += f'<div class="pp-col"><div class="pp-units">{units}</div><div class="lbl"><span>{label}</span><b>{count}</b></div></div>'
    legend = "".join(f'<span><i style="background:{LIFE_COLOURS[k]}"></i>{k} day{"s" if k > 1 else ""} left</span>' for k in range(5, 0, -1))
    legend += f'<span><i style="border:2px dashed {INK}; width:8px; height:12px"></i>To prepare today</span>'

    moves_html = ""
    for m in p["send"]:
        moves_html += (f'<div class="pp-move"><span class="c">{esc(CENTRE_NAMES[centre])} (this centre)</span><span class="arrow">→</span>'
                       f'<span class="c">{esc(m["to"].split(" - ")[1])}</span><span class="q">Send {m["units"]} · {m["minutes"]} min</span></div>')
    for m in p["receive"]:
        moves_html += (f'<div class="pp-move"><span class="c">{esc(m["from"].split(" - ")[1])}</span><span class="arrow">→</span>'
                       f'<span class="c">{esc(CENTRE_NAMES[centre])} (this centre)</span><span class="q">Receive {m["units"]} · {m["minutes"]} min</span></div>')
    if not moves_html:
        moves_html = '<div class="pp-empty">No transfers needed today. Nearby centres have no spare near-expiry units that this centre needs, and none are needed elsewhere.</div>'

    st.markdown(f"""
<div class="pp-panel pp-shelf">
  <h4>Platelet shelf: every unit on the agitator, by days of life left</h4>
  <div class="pp-cols">{cols}</div>
  <div class="pp-legend">{legend}</div>
</div>
<div class="pp-panel pp-moves"><h4>Transfers with nearby centres</h4>{moves_html}</div>
""", unsafe_allow_html=True)

    st.markdown("")
    rec = sysm.records[sysm.records["centre"] == centre].set_index("date")
    f0 = sysm.forecasts[centre]["f0"]
    win = rec.loc[d - pd.Timedelta(days=60):d]
    dfc = pd.DataFrame({"date": win.index, "Units issued": win["demand"].values, "Forecast": f0.loc[win.index].values}).melt("date", var_name="series", value_name="units")
    line = alt.Chart(dfc).mark_line(strokeWidth=2).encode(
        x=alt.X("date:T", title=None), y=alt.Y("units:Q", title="units per day"),
        color=alt.Color("series:N", scale=alt.Scale(domain=["Units issued", "Forecast"], range=[GREY, RED]), title=None),
        tooltip=[alt.Tooltip("date:T"), "series:N", alt.Tooltip("units:Q", format=".1f")],
    ).properties(height=260, title="Last 60 days: units issued and the forecast made each morning")
    st.altair_chart(styled(line), width="stretch", theme=None)
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
        sq, ours, base = ev.iloc[0], ev.iloc[3], ev.iloc[1]
        st.markdown(f"""
<div class="pp-caveat">In simulation, on a synthetic district of five centres: models were fitted on 2021–23, tuned on 2024 and tested on 2025, which they never saw.
These results show the method is worth testing on real registers. They are not a measured real-world saving.</div>
<div class="pp-panel"><div class="pp-kpis">
  <div class="pp-kpi"><div class="k">Platelets expired</div><div class="v"><span class="from">{sq['expiry_rate'] * 100:.1f}%</span> → {ours['expiry_rate'] * 100:.1f}%</div><div class="s">status quo vs PlateletPlan with transfers</div></div>
  <div class="pp-kpi"><div class="k">Units saved from expiry in 2025</div><div class="v">{int(sq['units_expired'] - ours['units_expired']):,}</div><div class="s">across the five centres</div></div>
  <div class="pp-kpi"><div class="k">Shortages vs a simple forecast</div><div class="v"><span class="from">{int(base['units_short'])}</span> → {int(ours['units_short'])}</div><div class="s">units short, 7-day average vs PlateletPlan</div></div>
</div></div>
""", unsafe_allow_html=True)
        st.markdown("")
        c1, c2 = st.columns([1, 1])
        bars = ev.assign(name=ev["policy"].map(SHORT), pct=ev["expiry_rate"] * 100)
        ch = alt.Chart(bars).mark_bar(cornerRadiusEnd=3, height=26).encode(
            y=alt.Y("name:N", sort=list(SHORT.values()), title=None),
            x=alt.X("pct:Q", title="% of prepared units that expired"),
            color=alt.Color("name:N", scale=alt.Scale(domain=list(SHORT.values()), range=[GREY, GREY, STRAW, RED]), legend=None),
            tooltip=[alt.Tooltip("name:N", title="Policy"), alt.Tooltip("pct:Q", format=".1f", title="Expiry %")])
        lbl = ch.mark_text(align="left", dx=5, color=INK, fontWeight=700).encode(text=alt.Text("pct:Q", format=".1f"))
        c1.altair_chart(styled((ch + lbl).properties(height=220, title="Expiry rate, test year 2025")), width="stretch", theme=None)
        sh = alt.Chart(bars).mark_bar(cornerRadiusEnd=3, height=26).encode(
            y=alt.Y("name:N", sort=list(SHORT.values()), title=None),
            x=alt.X("units_short:Q", title="units of demand not met"),
            color=alt.Color("name:N", scale=alt.Scale(domain=list(SHORT.values()), range=[GREY, GREY, STRAW, RED]), legend=None),
            tooltip=[alt.Tooltip("name:N", title="Policy"), alt.Tooltip("units_short:Q", title="Units short")])
        c2.altair_chart(styled((sh + sh.mark_text(align="left", dx=5, color=INK, fontWeight=700).encode(text="units_short:Q"))
                        .properties(height=220, title="Units short, test year 2025")), width="stretch", theme=None)

        st.markdown(f'<div class="pp-panel"><h4 style="margin-top:0">Normal season, 2025</h4>{eval_table(ev)}</div>', unsafe_allow_html=True)
        st.markdown("")
        if ev_s is not None:
            st.markdown(f'<div class="pp-panel"><h4 style="margin-top:0">Unseen outbreak: 2025 season twice as large and three weeks early</h4>{eval_table(ev_s)}'
                        f'<p class="pp-note">Transfers halve shortages compared with the 7-day average. The status quo holds so much extra stock that it runs short '
                        f'slightly less often, but it throws away about 7,000 more units. An outbreak mode that raises safety stock when cases climb is the next step.</p></div>',
                        unsafe_allow_html=True)
        st.markdown("")
        mon = load_eval("evaluation_by_month.csv")
        if mon is not None:
            mon = mon.assign(name=mon["policy"].map(SHORT), pct=mon["expired"] / mon["prepared"].clip(lower=1) * 100,
                             m=pd.to_datetime(mon["month"]))
            lc = alt.Chart(mon).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("m:T", title=None, axis=alt.Axis(format="%b")), y=alt.Y("pct:Q", title="% expired"),
                color=alt.Color("name:N", scale=alt.Scale(domain=list(SHORT.values()), range=[GREY, "#6E7785", STRAW, RED]), title=None),
                tooltip=["name:N", alt.Tooltip("m:T", format="%B"), alt.Tooltip("pct:Q", format=".1f")])
            st.altair_chart(styled(lc.properties(height=260, title="Expiry rate by month, 2025")), width="stretch", theme=None)
        if summ is not None:
            s = summ.set_index("policy")
            st.markdown(f'<p class="pp-note">Across three random seeds (7, 21, 42), PlateletPlan with transfers averages '
                        f'{s.loc["PlateletPlan + transfers", "expiry_rate_mean"] * 100:.1f}% expiry against '
                        f'{s.loc["Status quo (fixed share of donations)", "expiry_rate_mean"] * 100:.1f}% for the status quo and '
                        f'{s.loc["7-day average baseline", "expiry_rate_mean"] * 100:.1f}% for the 7-day average.</p>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Bring your own register
# ---------------------------------------------------------------------------
with tab_byo:
    st.markdown(f"""<div class="pp-panel"><h4 style="margin-top:0">Test PlateletPlan on a real centre's register</h4>
<p>Upload one blood centre's daily register as a CSV with the columns <b>date</b> and <b>issued</b> (platelet units issued that day),
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
            st.markdown(f"""<div class="pp-panel"><h4 style="margin-top:0">Replay of the last {out['test_days']} days</h4>
<table class="pp-table"><tr><th>Policy</th><th>Prepared</th><th>Expired</th><th>Expiry rate</th><th>Short</th><th>Shortage rate</th><th>Forecast error</th></tr>{rows}</table>
<div class="pp-why"><h4>Plan for {long_date(pd.Timestamp(t['date']))}</h4>
<div class="pp-reason"><span>Expected demand (next three days)</span><span class="v">{t['forecast'][0]} · {t['forecast'][1]} · {t['forecast'][2]} units</span></div>
<div class="pp-reason"><span>Keep this much usable stock</span><span class="v">{t['target_stock']} units</span></div>
<div class="pp-reason"><span>So prepare</span><span class="v">{t['target_stock']} minus usable units on hand, up to the donations available</span></div>
</div></div>""", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Could not read this register: {e}")

# ---------------------------------------------------------------------------
# Data and limits
# ---------------------------------------------------------------------------
with tab_about:
    doc = ROOT / "DATA.md"
    st.markdown(doc.read_text() if doc.exists() else "See DATA.md in the repository.")
