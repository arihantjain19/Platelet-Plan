"""Synthetic data generator: daily dengue cases, platelet demand and donations.

No public dataset of daily platelet demand at Indian blood centres exists, so this
module generates one. It is seeded and fully documented (docs/DATA.md) so anyone
can regenerate exactly the same data. It validates the METHOD, not real savings.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def _year_severity(year: int, scale: float = 1.0) -> float:
    vals = C.NCVBDC_ALL_INDIA_CASES
    mean = np.mean(list(vals.values()))
    return scale * vals.get(year, mean) / mean


def dengue_series(start=C.START, end=C.END, seed=7, outbreak_scale=1.0, peak_shift_weeks=0, shock_from_year=None) -> pd.DataFrame:
    """Daily district dengue cases with a post-monsoon seasonal peak.

    outbreak_scale / peak_shift_weeks let you create an *unseen* scenario, e.g. an
    outbreak twice as large that peaks three weeks earlier than usual. With
    shock_from_year set, the shock only applies from that year on, so models
    trained on earlier years have never seen anything like it.
    """
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    out = []
    for year in sorted(set(days.year)):
        ydays = days[days.year == year]
        doy = ydays.dayofyear.values
        shocked = shock_from_year is None or year >= shock_from_year
        peak = (C.DENGUE_PEAK_WEEK - (peak_shift_weeks if shocked else 0)) * 7
        bump = np.exp(-0.5 * ((doy - peak) / (C.DENGUE_SPREAD_WEEKS * 7)) ** 2)
        bump = bump / bump.sum()
        flat = np.full(len(doy), 1 / len(doy))
        share = (1 - C.DENGUE_BASELINE_SHARE) * bump + C.DENGUE_BASELINE_SHARE * flat
        total = C.DISTRICT_CASES_AVG_YEAR * _year_severity(year, outbreak_scale if shocked else 1.0)
        cases = rng.poisson(total * share)
        out.append(pd.DataFrame({"date": ydays, "dengue_cases": cases}))
    return pd.concat(out, ignore_index=True)


def demand_series(dengue: pd.DataFrame, seed=11) -> pd.DataFrame:
    """Daily platelet demand and whole-blood donations for every centre."""
    rng = np.random.default_rng(seed)
    d = dengue.copy()
    # weekly district cases (true, not lagged) drive real clinical demand
    d["weekly_cases"] = d["dengue_cases"].rolling(7, min_periods=1).sum()
    dow = d["date"].dt.dayofweek.values
    rows = []
    for c in C.CENTRES:
        mu = c.base_demand * np.array(C.DOW_FACTOR)[dow] + c.dengue_sensitivity * d["weekly_cases"].values / 100
        k = C.DEMAND_DISPERSION
        demand = rng.negative_binomial(k, k / (k + mu))
        don_mu = c.donations * np.array(C.DOW_DONATION)[dow]
        donations = rng.poisson(don_mu)
        rows.append(pd.DataFrame({"date": d["date"], "centre": c.code, "demand": demand, "donations": donations}))
    return pd.concat(rows, ignore_index=True)


def reported_dengue(dengue: pd.DataFrame) -> pd.DataFrame:
    """What a blood centre can actually see: last week's cases, one week late."""
    d = dengue.copy()
    weekly = d["dengue_cases"].rolling(7, min_periods=1).sum()
    d["reported_weekly_cases"] = weekly.shift(C.DENGUE_REPORTING_LAG_DAYS).bfill()
    return d[["date", "reported_weekly_cases"]]


def generate(seed=7, outbreak_scale=1.0, peak_shift_weeks=0, shock_from_year=None):
    dengue = dengue_series(seed=seed, outbreak_scale=outbreak_scale, peak_shift_weeks=peak_shift_weeks,
                           shock_from_year=shock_from_year)
    demand = demand_series(dengue, seed=seed + 4)
    signal = reported_dengue(dengue)
    return dengue, demand, signal


def travel_minutes() -> pd.DataFrame:
    """Approximate road travel time between centres (haversine x road factor)."""
    rows = []
    for a in C.CENTRES:
        for b in C.CENTRES:
            if a.code == b.code:
                continue
            lat1, lon1, lat2, lon2 = map(np.radians, [a.lat, a.lon, b.lat, b.lon])
            h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
            km = 2 * 6371 * np.arcsin(np.sqrt(h)) * C.ROAD_FACTOR
            rows.append({"from": a.code, "to": b.code, "km": round(km, 1), "minutes": round(km / C.ROAD_SPEED_KMH * 60)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).resolve().parents[1] / "data"
    out.mkdir(exist_ok=True)
    dengue, demand, signal = generate()
    dengue.merge(signal, on="date").to_csv(out / "dengue_district.csv", index=False)
    demand.to_csv(out / "centre_daily.csv", index=False)
    travel_minutes().to_csv(out / "travel_minutes.csv", index=False)
    # sample register in the format accepted by `cli register` / the app (Centre B, 2024-2025)
    reg = demand[(demand["centre"] == "B") & (demand["date"] >= "2024-01-01")][["date", "demand"]]
    reg = reg.rename(columns={"demand": "issued"}).merge(dengue[["date", "dengue_cases"]], on="date")
    reg.to_csv(out / "sample_register.csv", index=False)
    print(demand.groupby("centre")[["demand", "donations"]].mean().round(2))
