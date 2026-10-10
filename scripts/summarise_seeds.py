"""Combine test-year results from several random seeds into one table.

Run after:  python -m plateletplan.pipeline  (seed 7, results/)
            python -m plateletplan.pipeline --seed 21 --out results/seeds/seed_21
            python -m plateletplan.pipeline --seed 42 --out results/seeds/seed_42
"""
import pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1] / "results"
runs = {7: ROOT / "evaluation_test_year.csv"}
runs.update({int(p.name.split("_")[1]): p / "evaluation_test_year.csv" for p in (ROOT / "seeds").glob("seed_*")})
frames = [pd.read_csv(f).assign(seed=s) for s, f in sorted(runs.items()) if f.exists()]
df = pd.concat(frames)
df["weighted_cost"] = df["units_expired"] + 10 * df["units_short"]
summary = df.groupby("policy", sort=False).agg(
    seeds=("seed", "count"),
    expiry_rate_mean=("expiry_rate", "mean"), expiry_rate_min=("expiry_rate", "min"), expiry_rate_max=("expiry_rate", "max"),
    shortage_rate_mean=("shortage_rate", "mean"), shortage_rate_max=("shortage_rate", "max"),
    units_expired_mean=("units_expired", "mean"), units_short_mean=("units_short", "mean"),
    weighted_cost_mean=("weighted_cost", "mean")).reset_index()
df.to_csv(ROOT / "all_seeds_test_year.csv", index=False)
summary.to_csv(ROOT / "summary_across_seeds.csv", index=False)
show = summary.copy()
for c in [c for c in show if "rate" in c]:
    show[c] = (show[c] * 100).round(2)
print(show.round(1).to_string(index=False))
