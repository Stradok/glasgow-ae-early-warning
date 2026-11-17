"""Forecast engine (requirements R2 and R3): one-week-ahead forecast, risk class and drivers.

Model choice: the temperature-only GAM "M2t" from analysis/forecast_lib.py. Reasons (see analysis results):
  * the weather gain in the evaluation came from temperature; air quality, humidity and rain added nothing;
  * it needs only a temperature forecast, which exists for the coming week;
  * a GAM shows each term's effect, which is what R3 needs.
The same code is used for the evaluation and for the prototype.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "analysis"))
import forecast_lib as F  # noqa: E402

MODEL = "M2t"
LABELS = {
    "lag_1": "attendance last week", "lag_2": "attendance two weeks ago", "lag_52": "attendance same week last year",
    "woy": "time of year", "hol": "bank holidays this week", "hol_prev": "bank holidays last week",
    "temp_mean": "mean temperature this week", "temp_mean_l1": "mean temperature last week",
    "hot_days": "unusually warm days this week", "cold_days": "unusually cold days this week",
}


def append_target_week(weekly: pd.DataFrame, forecast_days: pd.DataFrame) -> pd.DataFrame:
    """Add the (unobserved) target week to the weekly history, with weather taken from the forecast."""
    row = {c: np.nan for c in weekly.columns}
    row["week_ending"] = pd.Timestamp(forecast_days["date"].max())
    row["temp_mean"] = float(forecast_days["tmean"].mean())
    row["temp_max"] = float(forecast_days["tmax"].max())
    row["temp_min"] = float(forecast_days["tmin"].min())
    return pd.concat([weekly, pd.DataFrame([row])], ignore_index=True)


def forecast_site(site: str, weekly: pd.DataFrame, daily_hist: pd.DataFrame, forecast_days: pd.DataFrame,
                  model: str = MODEL) -> dict:
    """Train on everything observed so far and forecast the week described by `forecast_days`.

    The target week must be the week directly after the last observed attendance week (horizon h = 1)."""
    cols = ["date", "tmean", "tmax", "tmin"]
    if len(forecast_days) != 7 or forecast_days[cols].isna().any().any():
        raise ValueError("the weather forecast must cover all 7 days of the target week with no missing values")
    dates = pd.to_datetime(forecast_days["date"]).reset_index(drop=True)
    if dates.iloc[-1].weekday() != 6 or not (dates.diff().dropna() == pd.Timedelta(days=1)).all():
        raise ValueError("the forecast days must be seven consecutive days, Monday to Sunday")
    last_obs = weekly.loc[weekly[f"att_{site}"].notna(), "week_ending"].max()
    target_we = pd.Timestamp(forecast_days["date"].max())
    if target_we != last_obs + pd.Timedelta(days=7):
        raise ValueError(f"target week {target_we.date()} is not the week after the last observed week "
                         f"{last_obs.date()}; this prototype forecasts one week ahead")
    full = append_target_week(weekly[weekly["week_ending"] <= last_obs], forecast_days)
    daily = pd.concat([daily_hist[["date", "tmax", "tmin"]], forecast_days[["date", "tmax", "tmin"]]],
                      ignore_index=True)
    daily = daily.drop_duplicates("date", keep="last")
    df = F.build_features(site, full, daily)
    names = F.feature_names(model, 1)
    tr = df.iloc[:-1].dropna(subset=names + ["y"])
    X, y = tr[names].values, tr["y"].values
    m = F.make_model(model, 1)
    m.tune(X, y)
    m.fit(X, y)
    x_new = df.iloc[[-1]][names]
    if x_new.isna().any().any():
        raise ValueError(f"missing inputs for the target week: {list(x_new.columns[x_new.isna().any()])}")
    fc = float(m.predict(x_new.values)[0])
    hist = df["y"].iloc[:-1].dropna().values
    contrib = m.contributions(x_new.values, X)
    drivers = sorted(((LABELS.get(k, k), v) for k, v in contrib.items()), key=lambda kv: -abs(kv[1]))
    p75, p90 = F.risk_thresholds(hist)
    return {"site": site, "target_week": target_we.date().isoformat(), "forecast": fc,
            "risk": F.risk_class(fc, hist), "last_week": float(hist[-1]), "p75": p75, "p90": p90,
            "drivers": drivers[:5], "model": model, "history": hist[-52:]}
