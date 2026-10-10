"""Daily plan for a blood centre: what the medical officer sees each morning.

Used by both the command line (cli.py) and the Streamlit app (app.py).
"""
from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

import pp_config as C
from pp_data import generate, travel_minutes
from pp_forecast import LassoForecaster, moving_average_frame, reason_text, wape
from pp_pipeline import build_forecasts
from pp_simulate import Policy, run, summarise

ROOT = pathlib.Path(__file__).resolve().parent
CENTRE_NAMES = {c.code: c.name for c in C.CENTRES}


def tuned_params(results_dir=ROOT):
    try:
        meta = json.loads((pathlib.Path(results_dir) / "run_meta.json").read_text())
        return meta["tuned"]["network"]["horizon"], meta["tuned"]["network"]["z"]
    except Exception:
        return 3, 0.75


@dataclass
class System:
    demand: pd.DataFrame
    signal: pd.DataFrame
    models: dict
    forecasts: dict
    sigma: dict
    records: pd.DataFrame
    moves: pd.DataFrame
    policy: Policy


def build_system(scenario: str = "normal", results_dir=ROOT) -> System:
    shock = dict(outbreak_scale=2.0, peak_shift_weeks=3, shock_from_year=2025) if scenario == "outbreak" else {}
    _, demand, signal = generate(**shock)
    travel = travel_minutes()
    models, lasso_f, lasso_sigma, _, _ = build_forecasts(demand, signal)
    H, z = tuned_params(results_dir)
    pol = Policy("PlateletPlan + transfers", "forecast", horizon=H, z=z, forecasts=lasso_f, sigma=lasso_sigma, transfers=True)
    rec, moves = run(pol, demand, travel, start=pd.Timestamp(C.TUNE_END) - pd.Timedelta(days=30), log=True)
    if moves.empty:
        moves = pd.DataFrame(columns=["date", "from", "to", "units", "minutes"])
    return System(demand, signal, models, lasso_f, lasso_sigma, rec, moves, pol)


def daily_plan(sys: System, date, centre: str) -> dict:
    date = pd.Timestamp(date)
    r = sys.records[(sys.records["date"] == date) & (sys.records["centre"] == centre)].iloc[0]
    f = sys.forecasts[centre].loc[date]
    hist = sys.demand[sys.demand["centre"] == centre].set_index("date")["demand"].astype(float)
    dengue = sys.signal.set_index("date")["reported_weekly_cases"]
    groups, row = sys.models[centre].explain(hist, dengue, date, h=0)
    d_now = float(dengue.loc[date])
    d_4w = float(dengue.shift(28).bfill().loc[date])
    stock_by_age = {f"{C.SHELF_LIFE_DAYS - a} day(s) left": int(r[f"age{a}"]) for a in range(C.SHELF_LIFE_DAYS)}
    moves = sys.moves[pd.to_datetime(sys.moves["date"]) == date]
    out_moves = moves[moves["from"] == centre]
    in_moves = moves[moves["to"] == centre]
    return {
        "date": date.date().isoformat(),
        "centre": centre,
        "centre_name": CENTRE_NAMES[centre],
        "forecast": {(date + pd.Timedelta(days=h)).date().isoformat(): round(float(f[f"f{h}"]), 1) for h in range(3)},
        "reason": reason_text(groups, row, d_now, d_4w, date),
        "stock_by_age": stock_by_age,
        "stock_total": int(sum(stock_by_age.values())),
        "donations_today": int(r["donations"]),
        "prepare_today": int(r["prepared"]),
        "send": [{"to": CENTRE_NAMES[m["to"]], "units": int(m["units"]), "minutes": int(m["minutes"])} for _, m in out_moves.iterrows()],
        "receive": [{"from": CENTRE_NAMES[m["from"]], "units": int(m["units"]), "minutes": int(m["minutes"])} for _, m in in_moves.iterrows()],
        "actual_demand": int(r["demand"]),
        "dengue_reported_weekly": round(d_now),
    }


def format_plan(p: dict) -> str:
    lines = [f"PlateletPlan · {p['centre_name']} · {p['date']}", ""]
    lines.append(f"PREPARE TODAY: {p['prepare_today']} platelet units (from {p['donations_today']} donations)")
    lines.append(f"Why: {p['reason']}")
    lines.append("Forecast demand: " + ", ".join(f"{d}: {v}" for d, v in p["forecast"].items()))
    lines.append(f"Stock this morning: {p['stock_total']} units (" + ", ".join(f"{k}: {v}" for k, v in p["stock_by_age"].items() if v) + ")")
    for m in p["send"]:
        lines.append(f"SEND {m['units']} near-expiry unit(s) to {m['to']} (~{m['minutes']} min)")
    for m in p["receive"]:
        lines.append(f"RECEIVE {m['units']} unit(s) from {m['from']} (~{m['minutes']} min)")
    lines.append(f"District dengue cases reported last week: {p['dengue_reported_weekly']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bring your own data: a single centre's daily issue register
# ---------------------------------------------------------------------------
def _simulate_single(demand: np.ndarray, forecasts: pd.DataFrame, sigma: float, H: int, z: float):
    L = C.SHELF_LIFE_DAYS
    stock = np.zeros(L, dtype=int)
    prepared = expired = short = 0
    for t, dem in enumerate(demand):
        need = sum(forecasts.iloc[t][f"f{h}"] for h in range(H)) + z * sigma * math.sqrt(H)
        q = max(0, math.ceil(need - stock.sum()))
        stock[0] += q
        prepared += q
        rem = int(dem)
        for a in range(L - 1, -1, -1):
            take = min(rem, stock[a])
            stock[a] -= take
            rem -= take
        short += rem
        expired += stock[L - 1]
        stock[1:] = stock[:-1].copy()
        stock[0] = 0
    return {"units_prepared": int(prepared), "units_expired": int(expired), "units_short": int(short),
            "expiry_rate": expired / max(prepared, 1), "shortage_rate": short / max(demand.sum(), 1)}


def plan_from_register(df: pd.DataFrame, shortage_weight: float = 10.0) -> dict:
    """df columns: date, issued [, dengue_cases]. Needs at least ~120 days.

    Fits on the first 70% of days, tunes and back-tests on the rest against the
    7-day-average baseline, then returns tomorrow's plan.
    """
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    if "date" not in df or "issued" not in df:
        raise ValueError("CSV needs columns 'date' and 'issued' (optional: 'dengue_cases')")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date").asfreq("D")
    df["issued"] = df["issued"].fillna(0).clip(lower=0)
    if len(df) < 120:
        raise ValueError(f"Need at least 120 days of history, got {len(df)}")
    hist = df["issued"].astype(float)
    if "dengue_cases" in df:
        dengue = df["dengue_cases"].fillna(0).rolling(7, min_periods=1).sum().shift(7).bfill()
    else:
        dengue = pd.Series(0.0, index=hist.index)
    split = hist.index[int(len(hist) * 0.7)]
    model = LassoForecaster().fit(hist[hist.index < split], dengue)
    lf = model.predict_frame(hist, dengue)
    mf = moving_average_frame(hist)
    test = hist.index >= split
    ma_sigma = float(np.std((hist - mf["f0"])[~test].dropna()))
    res = {}
    for name, fr, sg in (("PlateletPlan", lf, model.sigma[0]), ("7-day average", mf, ma_sigma)):
        best = None
        for H in (1, 2, 3):
            for z in np.arange(0, 3.01, 0.25):
                s = _simulate_single(hist[test].values, fr[test], sg, H, z)
                cost = s["units_expired"] + shortage_weight * s["units_short"]
                if best is None or cost < best[0]:
                    best = (cost, H, float(z), s)
        res[name] = {"horizon": best[1], "z": best[2], **best[3],
                     "wape": wape(hist[test].values, fr[test]["f0"].values)}
    # tomorrow's plan from the full history
    full = LassoForecaster().fit(hist, dengue)
    nxt = hist.index[-1] + pd.Timedelta(days=1)
    ext = pd.concat([hist, pd.Series([np.nan], index=[nxt])])
    dg = dengue.reindex(ext.index).ffill()
    f = full.predict_frame(ext.fillna(0), dg).loc[nxt]
    H, z = res["PlateletPlan"]["horizon"], res["PlateletPlan"]["z"]
    need = sum(f[f"f{h}"] for h in range(H)) + z * full.sigma[0] * math.sqrt(H)
    return {"backtest": res, "test_days": int(test.sum()),
            "tomorrow": {"date": nxt.date().isoformat(), "forecast": [round(float(f[f"f{h}"]), 1) for h in range(3)],
                         "target_stock": math.ceil(need),
                         "note": "Prepare (target_stock - usable units on hand), capped by donations."}}
