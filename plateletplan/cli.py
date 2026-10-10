"""Command line interface.

  python -m plateletplan.cli generate                       # write synthetic data to data/
  python -m plateletplan.cli evaluate                       # full evaluation -> results/
  python -m plateletplan.cli plan --centre A --date 2025-10-06
  python -m plateletplan.cli plan --centre A --date 2025-09-15 --scenario outbreak
  python -m plateletplan.cli register path/to/your_register.csv
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd


def main(argv=None):
    ap = argparse.ArgumentParser(prog="plateletplan", description="Platelet preparation and transfer planner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate", help="write the synthetic dataset to data/")
    ev = sub.add_parser("evaluate", help="run the full evaluation against baselines")
    ev.add_argument("--out", default=None)
    pl = sub.add_parser("plan", help="show the morning plan for one centre and date (test year 2025)")
    pl.add_argument("--centre", default="A", choices=list("ABCDE"))
    pl.add_argument("--date", default="2025-10-06")
    pl.add_argument("--scenario", default="normal", choices=["normal", "outbreak"])
    pl.add_argument("--json", action="store_true")
    rg = sub.add_parser("register", help="back-test and plan from your own daily issue register CSV")
    rg.add_argument("csv")
    a = ap.parse_args(argv)

    if a.cmd == "generate":
        import runpy
        runpy.run_module("plateletplan.data", run_name="__main__")
    elif a.cmd == "evaluate":
        from .pipeline import main as run_eval, ROOT
        run_eval(a.out or ROOT / "results")
    elif a.cmd == "plan":
        from .planner import build_system, daily_plan, format_plan
        d = pd.Timestamp(a.date)
        if not (pd.Timestamp("2025-01-01") <= d <= pd.Timestamp("2025-12-31")):
            sys.exit("Date must be in the 2025 test year (YYYY-MM-DD).")
        s = build_system(a.scenario)
        p = daily_plan(s, d, a.centre)
        print(json.dumps(p, indent=2) if a.json else format_plan(p))
    elif a.cmd == "register":
        from .planner import plan_from_register
        out = plan_from_register(pd.read_csv(a.csv))
        print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
