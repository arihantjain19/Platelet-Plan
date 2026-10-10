"""Day-by-day inventory simulation of a network of blood centres.

Each day, for every centre:
  1. (network policy only) near-expiry units are moved to centres that need them
  2. the policy decides how many platelet units to prepare from today's donations
  3. demand is served oldest-unit-first (FIFO); unmet demand is a shortage
  4. units that reach the end of their 5-day shelf life expire
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from ortools.graph.python import min_cost_flow

from . import config as C

L = C.SHELF_LIFE_DAYS


@dataclass
class Policy:
    name: str
    kind: str                     # "status_quo" | "forecast"
    share: float = 1.0            # status quo: fraction of donations made into platelets
    horizon: int = 2              # forecast: days of demand to cover
    z: float = 1.0                # forecast: safety factor (x forecast error std)
    transfers: bool = False
    forecasts: dict = field(default_factory=dict)  # centre -> DataFrame f0,f1,f2 indexed by date
    sigma: dict = field(default_factory=dict)      # centre -> forecast error std (h=0)


def _prep_quantity(p: Policy, code: str, date, stock: np.ndarray, donations: int, rng) -> int:
    if p.kind == "status_quo":
        return int(rng.binomial(donations, p.share))
    f = p.forecasts[code].loc[date]
    need = sum(f[f"f{h}"] for h in range(p.horizon)) + p.z * p.sigma[code] * math.sqrt(p.horizon)
    return int(min(donations, max(0, math.ceil(need - stock.sum()))))


def _plan_transfers(p: Policy, date, inv: dict, travel: dict):
    """Min-cost flow: near-expiry surplus -> centres short over the next two days."""
    surplus, deficit = {}, {}
    for code, stock in inv.items():
        f = p.forecasts[code].loc[date]
        f0, f1 = f["f0"], f["f1"]
        s4 = max(0.0, stock[L - 1] - f0)                       # expires tonight
        rem = max(0.0, f0 - stock[L - 1]) + f1
        s3 = max(0.0, stock[L - 2] - rem)                      # expires tomorrow night
        surplus[code] = int(math.floor(s4 + s3))
        need = f0 + f1 + p.z * p.sigma[code] * math.sqrt(2)
        deficit[code] = int(max(0, math.ceil(need - stock.sum())))
    src = [c for c in inv if surplus[c] > 0]
    dst = [c for c in inv if deficit[c] > 0]
    if not src or not dst:
        return []
    smcf = min_cost_flow.SimpleMinCostFlow()
    codes = list(inv)
    idx = {c: i + 1 for i, c in enumerate(codes)}              # 0 = source
    sink = len(codes) + 1
    out_node = {c: sink + 1 + i for i, c in enumerate(codes)}  # receiving side
    for c in src:
        smcf.add_arc_with_capacity_and_unit_cost(0, idx[c], surplus[c], 0)
    arcs = []
    for a in src:
        for b in dst:
            if a != b and travel[(a, b)] <= C.MAX_TRANSFER_MINUTES:
                arcs.append((smcf.add_arc_with_capacity_and_unit_cost(idx[a], out_node[b], 10_000, int(travel[(a, b)])), a, b))
    for b in dst:
        smcf.add_arc_with_capacity_and_unit_cost(out_node[b], sink, deficit[b], 0)
    total = min(sum(surplus.values()), sum(deficit.values()))
    smcf.set_node_supply(0, total)
    smcf.set_node_supply(sink, -total)
    # allow partial flow: add a bypass arc with high cost
    smcf.add_arc_with_capacity_and_unit_cost(0, sink, total, 1_000_000)
    if smcf.solve() != smcf.OPTIMAL:
        return []
    moves = []
    for arc, a, b in arcs:
        q = smcf.flow(arc)
        if q > 0:
            moves.append((a, b, int(q), int(travel[(a, b)])))
    return moves


def _take_oldest(stock: np.ndarray, q: int) -> np.ndarray:
    """Remove q units oldest-first; return removed units by age."""
    taken = np.zeros_like(stock)
    for age in range(L - 1, -1, -1):
        t = min(q, stock[age])
        stock[age] -= t
        taken[age] += t
        q -= t
        if q == 0:
            break
    return taken


def run(policy: Policy, demand: pd.DataFrame, travel_df: pd.DataFrame, start=None, end=None, seed=0, log=False):
    """Simulate the whole period. Returns daily records (one row per centre per day)."""
    rng = np.random.default_rng(seed)
    travel = {(r["from"], r["to"]): r["minutes"] for _, r in travel_df.iterrows()}
    pivot_d = demand.pivot(index="date", columns="centre", values="demand")
    pivot_s = demand.pivot(index="date", columns="centre", values="donations")
    dates = pivot_d.index
    if start is not None:
        dates = dates[dates >= pd.Timestamp(start)]
    if end is not None:
        dates = dates[dates <= pd.Timestamp(end)]
    codes = list(pivot_d.columns)
    inv = {c: np.zeros(L, dtype=int) for c in codes}
    recs, moves_log = [], []
    for date in dates:
        sent = {c: 0 for c in codes}
        recv = {c: 0 for c in codes}
        if policy.transfers:
            for a, b, q, mins in _plan_transfers(policy, date, inv, travel):
                units = _take_oldest(inv[a], q)
                inv[b] += units
                sent[a] += q
                recv[b] += q
                if log:
                    moves_log.append({"date": date, "from": a, "to": b, "units": q, "minutes": mins})
        for c in codes:
            stock = inv[c]
            ages_before = stock.copy()
            prepared = _prep_quantity(policy, c, date, stock, int(pivot_s.at[date, c]), rng)
            stock[0] += prepared
            on_hand = int(stock.sum())
            dem = int(pivot_d.at[date, c])
            issued = int(_take_oldest(stock, dem).sum())
            short = dem - issued
            expired = int(stock[L - 1])
            stock[1:] = stock[:-1].copy()
            stock[0] = 0
            recs.append({"date": date, "centre": c, "demand": dem, "prepared": prepared, "on_hand": on_hand,
                         "issued": issued, "shortage": short, "expired": expired,
                         "sent": sent[c], "received": recv[c], "end_stock": int(stock.sum()),
                         "donations": int(pivot_s.at[date, c]),
                         **{f"age{a}": int(ages_before[a]) for a in range(L)}})
    out = pd.DataFrame(recs)
    return (out, pd.DataFrame(moves_log)) if log else out


def summarise(rec: pd.DataFrame, start=None, end=None) -> dict:
    r = rec
    if start is not None:
        r = r[r["date"] >= pd.Timestamp(start)]
    if end is not None:
        r = r[r["date"] <= pd.Timestamp(end)]
    prepared, expired, demand, short = r["prepared"].sum(), r["expired"].sum(), r["demand"].sum(), r["shortage"].sum()
    return {
        "units_prepared": int(prepared),
        "units_expired": int(expired),
        "expiry_rate": expired / max(prepared, 1),
        "units_demanded": int(demand),
        "units_short": int(short),
        "shortage_rate": short / max(demand, 1),
        "units_transferred": int(r["sent"].sum()),
    }
