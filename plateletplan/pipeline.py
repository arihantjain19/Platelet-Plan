"""End-to-end pipeline: data -> forecasts -> calibrated status quo -> tuned policies -> evaluation.

Time split (never random):
  2021-2023  fit forecasting models, calibrate the status quo
  2024       tune policy parameters (horizon, safety factor)
  2025       untouched test year -> headline numbers
"""
from __future__ import annotations

import itertools
import json
import pathlib

import numpy as np
import pandas as pd

from . import config as C
from .data import generate, travel_minutes
from .forecast import LassoForecaster, moving_average_frame, wape
from .simulate import Policy, run, summarise

ROOT = pathlib.Path(__file__).resolve().parents[1]
TUNE_START = pd.Timestamp(C.TRAIN_END) + pd.Timedelta(days=1)
TEST_START = pd.Timestamp(C.TUNE_END) + pd.Timedelta(days=1)


def build_forecasts(demand: pd.DataFrame, signal: pd.DataFrame):
    dengue = signal.set_index("date")["reported_weekly_cases"]
    lasso_f, lasso_sigma, ma_f, ma_sigma, models = {}, {}, {}, {}, {}
    for code, g in demand.groupby("centre"):
        hist = g.set_index("date")["demand"].astype(float)
        train = hist[hist.index <= C.TRAIN_END]
        m = LassoForecaster().fit(train, dengue)
        models[code] = m
        lasso_f[code] = m.predict_frame(hist, dengue)
        lasso_sigma[code] = m.sigma[0]
        ma = moving_average_frame(hist)
        ma_f[code] = ma
        tr = ma.loc[:C.TRAIN_END, "f0"]
        ma_sigma[code] = float(np.std(train.values[7:] - tr.values[7:]))
    return models, lasso_f, lasso_sigma, ma_f, ma_sigma


def forecast_accuracy(demand, lasso_f, ma_f, start, end=None):
    rows = []
    for code, g in demand.groupby("centre"):
        hist = g.set_index("date")["demand"].astype(float)
        for h in (0, 1, 2):
            actual = hist.shift(-h)
            sel = (hist.index >= start) & (actual.notna())
            if end is not None:
                sel &= hist.index <= end
            rows.append({"centre": code, "horizon_days": h,
                         "wape_lasso": wape(actual[sel], lasso_f[code].loc[sel, f"f{h}"]),
                         "wape_ma7": wape(actual[sel], ma_f[code].loc[sel, f"f{h}"])})
    return pd.DataFrame(rows)


def calibrate_status_quo(demand, travel, target=C.STATUS_QUO_TARGET_EXPIRY):
    lo, hi = 0.2, 1.0
    for _ in range(14):
        mid = (lo + hi) / 2
        s = summarise(run(Policy("sq", "status_quo", share=mid), demand, travel, end=C.TRAIN_END), "2021-02-01", C.TRAIN_END)
        if s["expiry_rate"] < target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


SHORTAGE_WEIGHT = 10  # ASSUMPTION: one unit of unmet demand is as bad as 10 expired units


def tune(make_policy, demand, travel):
    """Grid-search horizon and safety factor on the tuning year (2024).

    Objective: expired units + SHORTAGE_WEIGHT x short units.
    """
    best, best_cost, grid = None, None, []
    for H, z in itertools.product((1, 2, 3), np.round(np.arange(0.0, 3.01, 0.25), 2)):
        p = make_policy(H, float(z))
        s = summarise(run(p, demand, travel, start=pd.Timestamp(C.TRAIN_END) - pd.Timedelta(days=30), end=C.TUNE_END), TUNE_START, C.TUNE_END)
        cost = s["units_expired"] + SHORTAGE_WEIGHT * s["units_short"]
        grid.append({"horizon": H, "z": float(z), "cost": cost, **s})
        if best_cost is None or cost < best_cost:
            best, best_cost = (H, float(z)), cost
    return best, pd.DataFrame(grid)


def main(outdir=ROOT / "results", outbreak_scale=1.0, peak_shift_weeks=0, shock_from_year=None, seed=7, verbose=True):
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    dengue, demand, signal = generate(seed=seed, outbreak_scale=outbreak_scale, peak_shift_weeks=peak_shift_weeks,
                                      shock_from_year=shock_from_year)
    travel = travel_minutes()
    models, lasso_f, lasso_sigma, ma_f, ma_sigma = build_forecasts(demand, signal)

    share = calibrate_status_quo(demand, travel)
    sq = Policy("Status quo (fixed share of donations)", "status_quo", share=share)
    sq_tune = summarise(run(sq, demand, travel, end=C.TUNE_END), TUNE_START, C.TUNE_END)
    if verbose:
        print(f"status quo share={share}, tune-year expiry={sq_tune['expiry_rate']:.1%} shortage={sq_tune['shortage_rate']:.1%}")

    def ma_pol(H, z):
        return Policy("7-day average baseline", "forecast", horizon=H, z=z, forecasts=ma_f, sigma=ma_sigma)

    def la_pol(H, z):
        return Policy("PlateletPlan (LASSO forecast)", "forecast", horizon=H, z=z, forecasts=lasso_f, sigma=lasso_sigma)

    def net_pol(H, z):
        return Policy("PlateletPlan + transfers", "forecast", horizon=H, z=z, forecasts=lasso_f, sigma=lasso_sigma, transfers=True)

    tuned, grids = {}, {}
    for key, mk in (("ma7", ma_pol), ("lasso", la_pol), ("network", net_pol)):
        tuned[key], grids[key] = tune(mk, demand, travel)
        if verbose:
            print(key, "tuned", tuned[key])

    policies = [sq, ma_pol(*tuned["ma7"]), la_pol(*tuned["lasso"]), net_pol(*tuned["network"])]
    rows, daily = [], {}
    for p in policies:
        rec, moves = run(p, demand, travel, start=pd.Timestamp(C.TUNE_END) - pd.Timedelta(days=30), log=True)
        daily[p.name] = rec
        s = summarise(rec, TEST_START)
        rows.append({"policy": p.name, "horizon": p.horizon if p.kind == "forecast" else None,
                     "z": p.z if p.kind == "forecast" else None, **s})
        if p.transfers:
            moves.to_csv(outdir / "transfers_test_year.csv", index=False)
    results = pd.DataFrame(rows)

    # per-centre and per-month breakdown for the test year
    per_centre = pd.concat([
        pd.DataFrame([{"policy": name, "centre": c, **summarise(g, TEST_START)} for c, g in rec.groupby("centre")])
        for name, rec in daily.items()])
    monthly = pd.concat([
        rec[rec["date"] >= TEST_START].assign(policy=name, month=lambda d: d["date"].dt.to_period("M").astype(str))
        .groupby(["policy", "month"])[["prepared", "expired", "demand", "shortage"]].sum().reset_index()
        for name, rec in daily.items()])

    acc = forecast_accuracy(demand, lasso_f, ma_f, TEST_START)
    results.to_csv(outdir / "evaluation_test_year.csv", index=False)
    per_centre.to_csv(outdir / "evaluation_by_centre.csv", index=False)
    monthly.to_csv(outdir / "evaluation_by_month.csv", index=False)
    acc.to_csv(outdir / "forecast_accuracy.csv", index=False)
    for k, g in grids.items():
        g.to_csv(outdir / f"tuning_grid_{k}.csv", index=False)
    meta = {"status_quo_share": share, "tuned": {k: {"horizon": v[0], "z": v[1]} for k, v in tuned.items()},
            "status_quo_tune_year": sq_tune, "shortage_weight": SHORTAGE_WEIGHT, "outbreak_scale": outbreak_scale, "peak_shift_weeks": peak_shift_weeks,
            "shock_from_year": shock_from_year, "seed": seed}
    (outdir / "run_meta.json").write_text(json.dumps(meta, indent=2, default=float))
    if verbose:
        pd.set_option("display.width", 200)
        show = results.copy()
        for c in ("expiry_rate", "shortage_rate"):
            show[c] = (show[c] * 100).round(1).astype(str) + "%"
        print(show.to_string(index=False))
        print(acc.groupby("horizon_days")[["wape_lasso", "wape_ma7"]].mean().round(3))
    return results, meta


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Run the full PlateletPlan evaluation")
    ap.add_argument("--out", default=str(ROOT / "results"))
    ap.add_argument("--outbreak-scale", type=float, default=1.0)
    ap.add_argument("--peak-shift-weeks", type=int, default=0)
    ap.add_argument("--shock-from-year", type=int, default=None)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    main(a.out, a.outbreak_scale, a.peak_shift_weeks, a.shock_from_year, a.seed)
