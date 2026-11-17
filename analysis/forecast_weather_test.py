"""Forecast-weather experiment (report Section 3.2.3, 'forecast-weather experiment').

Question: how much of the weather gain survives when the model is given the weather FORECAST that was
available at the time (not the observed reanalysis for the target week)?

Design
  * Archive: Open-Meteo Previous Runs API, ECMWF IFS 0.25 deg. Monday of the target week uses the forecast
    issued 1 day earlier (previous_day1), Tuesday previous_day2 ... Sunday previous_day7, so everything
    was known on the Sunday before the target week (horizon h = 1).
  * Models are TRAINED on reanalysis weather (as in the main experiment) and TESTED on forecast weather.
  * Air quality has no archived forecast here, so pm2_5/pm10 for the target week are replaced by the
    previous week's observed values (what an operator would know).
  * The archive only starts in early 2024, so the test window is shorter than the main 146 weeks.

    cd analysis && .venv/bin/python -I forecast_weather_test.py
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forecast_lib as F  # noqa: E402

OUT = os.path.join(F.HERE, "results")
CACHE = os.path.join(F.DATA, "forecast_previous_runs.json")
LAT, LON = 55.8642, -4.2518
MODEL = "ecmwf_ifs025"
VARS = ["temperature_2m", "relative_humidity_2m", "precipitation"]


def pull(start, end):
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    hourly = {"time": []}
    s = start
    while s <= end:
        e = min(end, s + dt.timedelta(days=59))
        q = {"latitude": LAT, "longitude": LON, "start_date": s.isoformat(), "end_date": e.isoformat(),
             "hourly": ",".join(f"{v}_previous_day{k}" for v in VARS for k in range(1, 8)),
             "models": MODEL, "timezone": "Europe/London"}
        for attempt in range(4):
            try:
                with urllib.request.urlopen("https://previous-runs-api.open-meteo.com/v1/forecast?"
                                            + urllib.parse.urlencode(q), timeout=120) as r:
                    d = json.load(r)["hourly"]
                break
            except Exception as ex:                     # retry on rate limit / network errors
                print("retry", s, ex)
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"could not pull {s}")
        hourly["time"] += d["time"]
        for k, v in d.items():
            if k != "time":
                hourly.setdefault(k, []).extend(v)
        s = e + dt.timedelta(days=1)
    json.dump(hourly, open(CACHE, "w"))
    return hourly


def weekly_forecast_features(hourly, df):
    """Weekly weather features for each target week built from the lead-appropriate forecasts."""
    h = pd.DataFrame(hourly)
    h["time"] = pd.to_datetime(h["time"])
    h["date"] = h["time"].dt.normalize()
    hot_thr, cold_thr = F.daily_weather_counts(df[["week_ending"]]).attrs["hot_thr"], \
        F.daily_weather_counts(df[["week_ending"]]).attrs["cold_thr"]
    rows = {}
    for we in df["week_ending"]:
        days = [we - pd.Timedelta(days=6 - j) for j in range(7)]     # Monday .. Sunday
        t_mean, t_max, t_min, hum, pr = [], [], [], [], []
        ok = True
        for j, d in enumerate(days):
            k = j + 1
            sub = h[h["date"] == d]
            if len(sub) < 24:
                ok = False
                break
            t = sub[f"temperature_2m_previous_day{k}"].values
            u = sub[f"relative_humidity_2m_previous_day{k}"].values
            p = sub[f"precipitation_previous_day{k}"].values
            if np.isnan(t.astype(float)).any() or np.isnan(u.astype(float)).any() or np.isnan(p.astype(float)).any():
                ok = False
                break
            t_mean.append(np.mean(t)); t_max.append(np.max(t)); t_min.append(np.min(t))
            hum.append(np.mean(u)); pr.append(np.sum(p))
        if ok:
            rows[we] = dict(temp_mean=np.mean(t_mean), temp_max=max(t_max), temp_min=min(t_min),
                            humidity_mean=np.mean(hum), precip_sum=float(np.sum(pr)),
                            hot_days=int(sum(x >= hot_thr for x in t_max)),
                            cold_days=int(sum(x <= cold_thr for x in t_min)))
    return pd.DataFrame.from_dict(rows, orient="index")


def main():
    base = F.build_features("QEUH")
    hourly = pull(dt.date(2024, 2, 1), dt.date(2026, 10, 25))
    fw = weekly_forecast_features(hourly, base)
    print("weeks with complete forecast data:", len(fw), fw.index.min(), "->", fw.index.max())
    recs, fcs = [], []
    acc = []
    for site in F.SITES:
        df = F.build_features(site)
        tdf = df.copy()
        idx = df.set_index("week_ending").index
        for c in fw.columns:
            tdf[c] = idx.map(fw[c]).values            # forecast weather for the target week
        tdf["temp_mean_l1"] = df["temp_mean_l1"]      # lags stay observed (known at the origin)
        tdf["temp_mean_l2"], tdf["precip_l1"] = df["temp_mean_l2"], df["precip_l1"]
        tdf["pm2_5_mean"], tdf["pm10_mean"] = df["pm2_5_l1"], df["pm10_mean"].shift(1)   # last week's observed values
        rows = [i for i in F.test_indices(df, 1) if df.at[i, "week_ending"] in fw.index]
        if site == "QEUH":
            both = df.iloc[rows]
            acc.append(("temp_mean", float(np.sqrt(np.mean((both["temp_mean"].values - tdf.iloc[rows]["temp_mean"].values) ** 2))),
                        float(np.mean(tdf.iloc[rows]["temp_mean"].values - both["temp_mean"].values))))
        b = F.baseline_forecasts(df, 1)
        b = b[b.week_ending.isin(df.iloc[rows]["week_ending"])]
        parts = [b]
        parts.append(F.rolling_forecasts(df, "M1", 1, test_rows=rows))
        parts.append(F.rolling_forecasts(df, "M2", 1, test_rows=rows).assign(model="M2_nowcast"))
        parts.append(F.rolling_forecasts(df, "M2", 1, test_df=tdf, test_rows=rows).assign(model="M2_forecastwx"))
        parts.append(F.rolling_forecasts(df, "M2t", 1, test_rows=rows).assign(model="M2t_nowcast"))
        parts.append(F.rolling_forecasts(df, "M2t", 1, test_df=tdf, test_rows=rows).assign(model="M2t_forecastwx"))
        m3 = [F.rolling_forecasts(df, "M3", 1, seed=s, test_df=tdf, test_rows=rows) for s in (0, 1, 2)]
        r3 = m3[0].copy(); r3["forecast"] = np.mean([x["forecast"].values for x in m3], axis=0)
        parts.append(r3.assign(model="M3_forecastwx"))
        site_fc = pd.concat(parts, ignore_index=True).assign(site=site)
        fcs.append(site_fc)
    fc = pd.concat(fcs, ignore_index=True)
    fc["error"] = fc["actual"] - fc["forecast"]
    fc.to_csv(os.path.join(OUT, "forecastwx_forecasts.csv"), index=False)
    met = fc.groupby(["site", "model"]).apply(lambda g: pd.Series({"n": len(g), "MAE": F.mae(g.actual, g.forecast),
                                                                   "MAPE": F.mape(g.actual, g.forecast)}), include_groups=False).reset_index()
    ref = met[met.model == "B2"].set_index("site")["MAE"]
    met["skill_vs_B2"] = [1 - r.MAE / ref[r.site] for r in met.itertuples()]
    met.to_csv(os.path.join(OUT, "forecastwx_metrics.csv"), index=False)
    pairs = [("M2_forecastwx", "M1"), ("M2_forecastwx", "B2"), ("M2_forecastwx", "M2_nowcast"), ("M2_nowcast", "M1"),
             ("M3_forecastwx", "B2"), ("M3_forecastwx", "M1"),
             ("M2t_forecastwx", "M1"), ("M2t_forecastwx", "B2"), ("M2t_forecastwx", "M2_forecastwx")]
    recs = []
    for s in F.SITES:
        piv = fc[fc.site == s].pivot(index="week_ending", columns="model", values="error")
        for a, b_ in pairs:
            stat, p, d = F.diebold_mariano(piv[a].values, piv[b_].values, 1)
            recs.append(dict(site=s, model_a=a, model_b=b_, mean_abs_err_diff=d, dm_stat=stat, p_raw=p))
    dm = pd.DataFrame(recs)
    dm["p_holm"] = np.nan
    for (a, b_), g in dm[dm.site.isin(["QEUH", "GRI"])].groupby(["model_a", "model_b"]):
        adj = F.holm({r.site: r.p_raw for r in g.itertuples()})
        for i, r in g.iterrows():
            dm.loc[i, "p_holm"] = adj[r.site]
    dm.to_csv(os.path.join(OUT, "forecastwx_dm.csv"), index=False)
    pd.set_option("display.width", 200)
    print("forecast quality of weekly mean temperature vs reanalysis (QEUH weeks): RMSE %.2f C, bias %.2f C" % acc[0][1:])
    print(met.pivot(index="model", columns="site", values="MAE").round(1))
    print(met.pivot(index="model", columns="site", values="skill_vs_B2").round(3))
    print(dm.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
