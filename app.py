"""PlateletPlan - Streamlit app.  Run:  streamlit run app.py"""
import pathlib

import altair as alt
import pandas as pd
import streamlit as st

import pp_config as C
from pp_planner import build_system, daily_plan, plan_from_register

ROOT = pathlib.Path(__file__).resolve().parent
RES = ROOT  # all result files sit next to app.py

st.set_page_config(page_title="PlateletPlan", page_icon="🩸", layout="wide")
st.title("PlateletPlan")
st.caption("Forecasting and rebalancing short-life platelet stock across a district's blood centres. "
           "All centre-level data shown here is SYNTHETIC (see Data & limits).")


@st.cache_resource(show_spinner="Training forecasts and simulating the district…")
def get_system(scenario):
    return build_system(scenario)


tab_plan, tab_eval, tab_byo, tab_about = st.tabs(["Today's plan", "Evaluation", "Use your own register", "Data & limits"])

qp = st.query_params  # optional deep link: ?centre=B&date=2025-10-03&scenario=outbreak
codes = [c.code for c in C.CENTRES]
q_centre = qp.get("centre", "A") if qp.get("centre", "A") in codes else "A"
try:
    q_date = pd.Timestamp(qp.get("date", "2025-10-06"))
except Exception:
    q_date = pd.Timestamp("2025-10-06")
q_scen = qp.get("scenario", "normal") if qp.get("scenario", "normal") in ("normal", "outbreak") else "normal"

with tab_plan:
    c1, c2, c3 = st.columns([2, 2, 2])
    centre = c1.selectbox("Blood centre", codes, index=codes.index(q_centre), format_func=lambda k: {c.code: c.name for c in C.CENTRES}[k])
    date = c2.date_input("Date (2025 test year)", q_date, min_value=pd.Timestamp("2025-01-01"), max_value=pd.Timestamp("2025-12-29"))
    scenario = c3.radio("Scenario", ["normal", "outbreak"], index=["normal", "outbreak"].index(q_scen), horizontal=True,
                        help="outbreak = 2x larger dengue season peaking 3 weeks early in 2025, never seen in training")
    sysm = get_system(scenario)
    p = daily_plan(sysm, pd.Timestamp(date), centre)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Prepare today", f"{p['prepare_today']} units", help="from today's donations")
    m2.metric("Forecast today", f"{list(p['forecast'].values())[0]:.0f} units")
    m3.metric("Stock this morning", f"{p['stock_total']} units")
    m4.metric("Dengue cases reported last week", p["dengue_reported_weekly"])
    st.info(f"**Why:** {p['reason']}")
    for m in p["send"]:
        st.warning(f"**Send {m['units']} near-expiry unit(s)** to {m['to']} (about {m['minutes']} min by road)")
    for m in p["receive"]:
        st.success(f"**Receive {m['units']} unit(s)** from {m['from']} (about {m['minutes']} min) — prepare fewer new units")

    left, right = st.columns(2)
    with left:
        st.subheader("Stock by days of life left")
        sb = pd.DataFrame({"days left": list(p["stock_by_age"].keys()), "units": list(p["stock_by_age"].values())})
        st.altair_chart(alt.Chart(sb).mark_bar(color="#1f5fbf").encode(x=alt.X("days left", sort=None), y="units"), width='stretch')
    with right:
        st.subheader("Demand: actual vs forecast (last 60 days)")
        rec = sysm.records[sysm.records["centre"] == centre].set_index("date")
        f0 = sysm.forecasts[centre]["f0"]
        win = rec.loc[pd.Timestamp(date) - pd.Timedelta(days=60):pd.Timestamp(date)]
        dfc = pd.DataFrame({"date": win.index, "actual": win["demand"].values, "forecast": f0.loc[win.index].values}).melt("date")
        st.altair_chart(alt.Chart(dfc).mark_line().encode(x="date:T", y="value:Q", color="variable:N"), width='stretch')
    st.caption(f"Actual demand that day (known only afterwards): {p['actual_demand']} units.")

with tab_eval:
    st.subheader("Test year 2025 — all five centres")
    def show_eval(path, title):
        if not path.exists():
            st.warning(f"Run `python pp_pipeline.py` first ({path.name} missing)")
            return
        ev = pd.read_csv(path)
        disp = ev[["policy", "units_prepared", "units_expired", "expiry_rate", "units_short", "shortage_rate", "units_transferred"]].copy()
        disp["expiry_rate"] = (disp["expiry_rate"] * 100).round(1).astype(str) + "%"
        disp["shortage_rate"] = (disp["shortage_rate"] * 100).round(2).astype(str) + "%"
        st.markdown(f"**{title}**")
        st.dataframe(disp, hide_index=True, width='stretch')
    show_eval(RES / "evaluation_test_year.csv", "Normal season (models fitted 2021–23, tuned on 2024, tested on 2025)")
    show_eval(RES / "stress_evaluation_test_year.csv", "Unseen outbreak: 2025 season 2x larger and 3 weeks early")
    mon = RES / "evaluation_by_month.csv"
    if mon.exists():
        m = pd.read_csv(mon)
        m["expired %"] = m["expired"] / m["prepared"].clip(lower=1) * 100
        st.markdown("**Expiry rate by month, 2025**")
        st.altair_chart(alt.Chart(m).mark_line(point=True).encode(x="month:N", y="expired %:Q", color="policy:N"), width='stretch')
    acc = RES / "forecast_accuracy.csv"
    if acc.exists():
        a = pd.read_csv(acc).groupby("horizon_days")[["wape_lasso", "wape_ma7"]].mean().reset_index()
        a.columns = ["days ahead", "LASSO error (WAPE)", "7-day average error (WAPE)"]
        st.markdown("**Forecast error, 2025 (weighted absolute % error; lower is better)**")
        st.dataframe(a.round(3), hide_index=True)

with tab_byo:
    st.write("Upload a daily register for **one** blood centre: columns `date`, `issued` "
             "(platelet units issued that day) and optionally `dengue_cases` (district daily cases). "
             "At least 120 days. The tool fits on the first 70%, back-tests on the rest against a 7-day average, "
             "and gives tomorrow's target stock.")
    sample = ROOT / "sample_register.csv"
    if sample.exists():
        st.download_button("Download a sample register", sample.read_bytes(), "sample_register.csv")
    up = st.file_uploader("Register CSV", type="csv")
    if up is not None:
        try:
            out = plan_from_register(pd.read_csv(up))
            bt = pd.DataFrame(out["backtest"]).T
            bt["expiry_rate"] = (bt["expiry_rate"].astype(float) * 100).round(1).astype(str) + "%"
            bt["shortage_rate"] = (bt["shortage_rate"].astype(float) * 100).round(2).astype(str) + "%"
            st.markdown(f"**Back-test over the last {out['test_days']} days**")
            st.dataframe(bt, width='stretch')
            t = out["tomorrow"]
            st.success(f"**{t['date']}** — forecast {t['forecast'][0]} units (next days {t['forecast'][1]}, {t['forecast'][2]}). "
                       f"Target usable stock: **{t['target_stock']} units**. {t['note']}")
        except Exception as e:
            st.error(str(e))

with tab_about:
    st.markdown((ROOT / "DATA.md").read_text() if (ROOT / "DATA.md").exists() else "See DATA.md")
