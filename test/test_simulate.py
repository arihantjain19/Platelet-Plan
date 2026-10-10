import numpy as np
import pandas as pd

from plateletplan import config as C
from plateletplan.data import generate, travel_minutes
from plateletplan.simulate import Policy, run, _take_oldest


def _flat_demand(days=20, dem=3, don=10, centres=("A",)):
    dates = pd.date_range("2025-01-01", periods=days)
    return pd.DataFrame([{"date": d, "centre": c, "demand": dem, "donations": don} for d in dates for c in centres])


def test_oldest_units_are_issued_first():
    stock = np.array([2, 0, 3, 0, 1])
    taken = _take_oldest(stock, 2)
    assert list(taken) == [0, 0, 1, 0, 1]
    assert list(stock) == [2, 0, 2, 0, 0]


def test_units_expire_after_shelf_life():
    # prepare 10 units a day, use 3 (oldest first): nothing can expire before day 5,
    # and in steady state the 7 surplus units a day expire.
    d = _flat_demand(days=20)
    rec = run(Policy("all", "status_quo", share=1.0), d, travel_minutes())
    assert (rec["expired"].iloc[: C.SHELF_LIFE_DAYS - 1] == 0).all()
    assert (rec["expired"].iloc[10:] == 7).all()
    assert rec["on_hand"].max() <= 10 * C.SHELF_LIFE_DAYS


def test_units_are_conserved():
    _, demand, _ = generate()
    demand = demand[demand["date"] <= "2021-03-31"]
    rec = run(Policy("sq", "status_quo", share=0.6), demand, travel_minutes())
    for _, g in rec.groupby("centre"):
        inflow = g["prepared"].sum() + g["received"].sum()
        outflow = g["issued"].sum() + g["expired"].sum() + g["sent"].sum() + g["end_stock"].iloc[-1]
        assert inflow == outflow


def test_shortage_counted_when_no_supply():
    d = _flat_demand(days=5, dem=4, don=0)
    rec = run(Policy("none", "status_quo", share=1.0), d, travel_minutes())
    assert rec["shortage"].sum() == 20


def test_data_is_reproducible():
    a = generate(seed=7)[1]
    b = generate(seed=7)[1]
    pd.testing.assert_frame_equal(a, b)


def test_units_are_conserved_with_transfers():
    from plateletplan.forecast import moving_average_frame
    _, demand, _ = generate()
    demand = demand[demand["date"] <= "2021-06-30"]
    f, sg = {}, {}
    for c, g in demand.groupby("centre"):
        f[c] = moving_average_frame(g.set_index("date")["demand"].astype(float))
        sg[c] = 1.0
    rec = run(Policy("net", "forecast", horizon=3, z=2.0, forecasts=f, sigma=sg, transfers=True), demand, travel_minutes())
    assert rec["sent"].sum() == rec["received"].sum()
    assert rec["sent"].sum() > 0
    for _, g in rec.groupby("centre"):
        inflow = g["prepared"].sum() + g["received"].sum()
        outflow = g["issued"].sum() + g["expired"].sum() + g["sent"].sum() + g["end_stock"].iloc[-1]
        assert inflow == outflow
