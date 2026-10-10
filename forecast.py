"""Demand forecasting: LASSO model and the moving-average baseline.

At the start of day t the centre knows demand up to day t-1 and the dengue
figures reported so far. It forecasts demand for days t, t+1, t+2 (h = 0, 1, 2).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LassoCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZONS = (0, 1, 2)
DOW_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# feature name -> human-readable group used in explanations
FEATURE_GROUPS = {
    **{f"lag{i}": "recent usage" for i in range(1, 8)},
    "ma7": "recent usage", "ma28": "recent usage",
    **{f"dow{i}": "day of week" for i in range(7)},
    "dengue": "dengue cases", "dengue_trend": "dengue cases",
}


def build_features(hist: pd.Series, dengue: pd.Series, h: int) -> pd.DataFrame:
    """hist: daily demand indexed by date. dengue: reported weekly cases indexed by date.

    Row for date t = information available on the morning of t, target = demand on t+h.
    """
    df = pd.DataFrame(index=hist.index)
    for i in range(1, 8):
        df[f"lag{i}"] = hist.shift(i)
    df["ma7"] = hist.shift(1).rolling(7).mean()
    df["ma28"] = hist.shift(1).rolling(28).mean()
    target_dow = (hist.index + pd.Timedelta(days=h)).dayofweek
    for i in range(7):
        df[f"dow{i}"] = (target_dow == i).astype(float)
    dg = dengue.reindex(hist.index).ffill().bfill()
    df["dengue"] = dg
    df["dengue_trend"] = dg - dg.shift(28).bfill()
    return df


def target(hist: pd.Series, h: int) -> pd.Series:
    return hist.shift(-h)


class LassoForecaster:
    """One LASSO model per horizon for one centre."""

    def __init__(self):
        self.models, self.sigma, self.means = {}, {}, {}

    def fit(self, hist: pd.Series, dengue: pd.Series):
        for h in HORIZONS:
            X = build_features(hist, dengue, h)
            y = target(hist, h)
            ok = X.notna().all(axis=1) & y.notna()
            X, y = X[ok], y[ok]
            m = make_pipeline(StandardScaler(), LassoCV(cv=TimeSeriesSplit(5), max_iter=20000))
            m.fit(X.values, y.values)
            self.models[h] = m
            self.sigma[h] = float(np.std(y.values - m.predict(X.values)))
            self.means[h] = X.mean()
        self.columns = list(X.columns)
        return self

    def predict_frame(self, hist: pd.Series, dengue: pd.Series) -> pd.DataFrame:
        """Forecasts for every date in hist (row t -> demand on t+h), columns f0,f1,f2."""
        out = pd.DataFrame(index=hist.index)
        for h in HORIZONS:
            X = build_features(hist, dengue, h).ffill().bfill()
            out[f"f{h}"] = np.clip(self.models[h].predict(X.values), 0, None)
        return out

    def explain(self, hist: pd.Series, dengue: pd.Series, date, h: int = 0, top: int = 3):
        """Contribution of each feature group vs an average day, in units."""
        X = build_features(hist, dengue, h).ffill().bfill().loc[[date]]
        scaler, lasso = self.models[h].named_steps["standardscaler"], self.models[h].named_steps["lassocv"]
        z = (X.values[0] - scaler.mean_) / scaler.scale_
        contrib = pd.Series(lasso.coef_ * z, index=self.columns)
        groups = contrib.groupby(lambda c: FEATURE_GROUPS[c]).sum().sort_values(key=np.abs, ascending=False)
        return groups.head(top), X.iloc[0]


def moving_average_frame(hist: pd.Series, window: int = 7) -> pd.DataFrame:
    ma = hist.shift(1).rolling(window, min_periods=1).mean().bfill()
    return pd.DataFrame({f"f{h}": ma for h in HORIZONS}, index=hist.index)


def reason_text(groups: pd.Series, row: pd.Series, dengue_now: float, dengue_4w: float, target_date) -> str:
    parts = []
    for name, val in groups.items():
        if abs(val) < 0.3:
            continue
        sign = "+" if val > 0 else "−"
        if name == "dengue cases":
            change = (dengue_now - dengue_4w) / max(dengue_4w, 1) * 100
            parts.append(f"dengue cases {dengue_now:.0f}/week ({change:+.0f}% vs 4 weeks ago) {sign}{abs(val):.1f}")
        elif name == "day of week":
            parts.append(f"{DOW_NAMES[pd.Timestamp(target_date).dayofweek]} {sign}{abs(val):.1f}")
        else:
            parts.append(f"recent usage {row['ma7']:.1f}/day {sign}{abs(val):.1f}")
    return "; ".join(parts) if parts else "close to a normal day"


def wape(actual, forecast) -> float:
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    return float(np.abs(actual - forecast).sum() / max(actual.sum(), 1e-9))
