"""Fetch the latest data (requirement R1): attendance, observed weather, weather forecast.

The history is re-pulled with the SAME functions as analysis/build_dataset.py (single source of truth),
but into this prototype's own data folder, so the frozen analysis dataset used in the report is never
overwritten.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(os.path.dirname(HERE), "analysis")
DATA = os.path.join(HERE, "data")
sys.path.insert(0, ANALYSIS)
import build_dataset as bd  # noqa: E402  (the report's own data-building code)


def last_complete_sunday(today: dt.date | None = None, lag_days: int = 6) -> dt.date:
    """Latest Sunday whose whole week is old enough for the reanalysis archive (about 5 days' delay)."""
    today = today or dt.date.today()
    d = today - dt.timedelta(days=lag_days)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def refresh_history(data_dir: str = DATA, today: dt.date | None = None) -> str:
    """Re-pull attendance, weather and air quality up to the last complete week. Returns the CSV path."""
    os.makedirs(data_dir, exist_ok=True)
    bd.DATA = data_dir
    bd.END = last_complete_sunday(today)
    bd.main()
    return os.path.join(data_dir, "weekly_dataset.csv")


def load_history(data_dir: str = DATA) -> pd.DataFrame:
    path = os.path.join(data_dir, "weekly_dataset.csv")
    if not os.path.exists(path):          # fall back to the frozen analysis dataset (offline demo)
        path = os.path.join(ANALYSIS, "data", "weekly_dataset.csv")
    df = pd.read_csv(path, parse_dates=["week_ending"]).sort_values("week_ending").reset_index(drop=True)
    return df


def load_daily_weather(data_dir: str = DATA) -> pd.DataFrame:
    path = os.path.join(data_dir, "raw_weather_daily.json")
    if not os.path.exists(path):
        path = os.path.join(ANALYSIS, "data", "raw_weather_daily.json")
    w = json.load(open(path))
    return pd.DataFrame({"date": pd.to_datetime(w["time"]), "tmax": w["temperature_2m_max"],
                         "tmin": w["temperature_2m_min"]})


def fetch_forecast_days(week_ending: dt.date) -> pd.DataFrame:
    """Daily forecast weather for the Monday-Sunday week ending `week_ending` (Open-Meteo forecast API).
    Returns date, tmean, tmax, tmin. Needs network access."""
    q = {"latitude": bd.LAT, "longitude": bd.LON, "timezone": "Europe/London", "past_days": 31, "forecast_days": 16,
         "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min"}
    with urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q), timeout=60) as r:
        d = json.load(r)["daily"]
    out = pd.DataFrame({"date": pd.to_datetime(d["time"]), "tmean": d["temperature_2m_mean"],
                        "tmax": d["temperature_2m_max"], "tmin": d["temperature_2m_min"]})
    start = pd.Timestamp(week_ending) - pd.Timedelta(days=6)
    wk = out[(out["date"] >= start) & (out["date"] <= pd.Timestamp(week_ending))]
    if len(wk) < 7 or wk[["tmean", "tmax", "tmin"]].isna().any().any():
        raise RuntimeError(f"forecast for the week ending {week_ending} is not available yet (needs 7 days)")
    return wk.reset_index(drop=True)
