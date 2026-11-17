"""Shared code: features, models and rolling-origin evaluation for weekly A&E forecasting.

Design follows report Section 3.2 (models B1, B2, M1, M2, M3) and 3.2.3 (evaluation).
All functions are importable so the prototype and the tests use the same code.

Conventions
- week_ending is the Sunday that ends a Monday-Sunday week.
- Forecast horizon h: the forecast for week t is made with information up to week t-h.
- A model for horizon h uses only attendance lags >= h (direct multi-step strategy).
- Weather and air quality for the TARGET week are observed (ERA5-Land / CAMS reanalysis), so
  M2/M3 results are a "nowcast" upper bound on what weather can add (see forecast_weather_test.py).
"""
from __future__ import annotations

import json
import os
import warnings

import holidays as _holidays
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SITES = ["QEUH", "GRI", "RHC"]
TEST_START = pd.Timestamp("2024-01-01")   # same chronological split as the interim baselines
FLAG_FRACTION = 0.6                        # flag weeks below 60% of the site median (interim rule)
RETUNE_EVERY = 26                          # weeks between hyper-parameter searches (inside training data)

# ------------------------------------------------------------------ feature sets
CALENDAR = ["woy", "hol", "hol_prev"]
WEATHER_GAM = ["temp_mean", "temp_mean_l1", "humidity_mean", "precip_sum",
               "pm2_5_mean", "pm10_mean", "hot_days", "cold_days"]
WEATHER_XGB = WEATHER_GAM + ["temp_max", "temp_min", "temp_mean_l2", "precip_l1", "pm2_5_l1"]
# weather groups for the ablation (which environmental factors matter)
GROUPS = {"M2t": ["temp_mean", "temp_mean_l1", "hot_days", "cold_days"],   # temperature
          "M2a": ["pm2_5_mean", "pm10_mean"],                               # air quality
          "M2w": ["humidity_mean", "precip_sum"]}                           # humidity and rain


def ar_cols(h: int) -> list[str]:
    return [f"lag_{h}", f"lag_{h + 1}", "lag_52"]


def feature_names(model: str, h: int) -> list[str]:
    """Column order matters for the GAM term list below."""
    base = ar_cols(h) + CALENDAR
    if model in ("M1", "M3a"):
        return base
    if model == "M2":
        return base + WEATHER_GAM
    if model == "M3":
        return base + WEATHER_XGB
    if model in GROUPS:
        return base + GROUPS[model]
    raise ValueError(model)


# ------------------------------------------------------------------ data
def load_weekly() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(DATA, "weekly_dataset.csv"), parse_dates=["week_ending"])
    return df.sort_values("week_ending").reset_index(drop=True)


def daily_weather_counts(df: pd.DataFrame, daily: pd.DataFrame | None = None) -> pd.DataFrame:
    """Hot / cold day counts per week. Thresholds are percentiles of daily data BEFORE the test
    period (90th of Tmax, 10th of Tmin), so no test information leaks into the features."""
    if daily is None:
        w = json.load(open(os.path.join(DATA, "raw_weather_daily.json")))
        d = pd.DataFrame({"date": pd.to_datetime(w["time"]),
                          "tmax": w["temperature_2m_max"], "tmin": w["temperature_2m_min"]})
    else:
        d = daily[["date", "tmax", "tmin"]].copy()
        d["date"] = pd.to_datetime(d["date"])
    train = d[d["date"] < TEST_START]
    hot_thr = float(np.percentile(train["tmax"].dropna(), 90))
    cold_thr = float(np.percentile(train["tmin"].dropna(), 10))
    d["hot"] = (d["tmax"] >= hot_thr).astype(int)
    d["cold"] = (d["tmin"] <= cold_thr).astype(int)
    # Monday-Sunday week ending on Sunday
    d["week_ending"] = d["date"] + pd.to_timedelta((6 - d["date"].dt.day_of_week), unit="D")
    g = d.groupby("week_ending")[["hot", "cold"]].sum().rename(columns={"hot": "hot_days", "cold": "cold_days"})
    out = df[["week_ending"]].merge(g, on="week_ending", how="left")
    out.attrs["hot_thr"], out.attrs["cold_thr"] = hot_thr, cold_thr
    return out


def holiday_counts(week_endings: pd.Series) -> np.ndarray:
    years = range(week_endings.dt.year.min() - 1, week_endings.dt.year.max() + 2)
    hol = _holidays.country_holidays("GB", subdiv="SCT", years=years)
    hdates = {pd.Timestamp(k) for k in hol.keys()}
    out = []
    for we in week_endings:
        days = [we - pd.Timedelta(days=k) for k in range(7)]
        out.append(sum(d in hdates for d in days))
    return np.array(out, float)


def build_features(site: str, weekly: pd.DataFrame | None = None,
                   daily: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per week with the target, flags and every candidate feature."""
    weekly = load_weekly() if weekly is None else weekly
    df = weekly.copy()
    cnt = daily_weather_counts(df, daily)
    df["hot_days"], df["cold_days"] = cnt["hot_days"].values, cnt["cold_days"].values
    df["y"] = df[f"att_{site}"].astype(float)
    med = df.loc[df["week_ending"] < TEST_START, "y"].median()   # pre-test median: no look-ahead
    df["flagged"] = (df["y"] < FLAG_FRACTION * med).astype(int)
    for k in range(1, 8):
        df[f"lag_{k}"] = df["y"].shift(k)
    df["lag_52"] = df["y"].shift(52)
    for c, name in (("temp_mean", "temp_mean_l1"),):
        df[name] = df[c].shift(1)
    df["temp_mean_l2"] = df["temp_mean"].shift(2)
    df["precip_l1"] = df["precip_sum"].shift(1)
    df["pm2_5_l1"] = df["pm2_5_mean"].shift(1)
    # week of year on a 1..52 scale (periodic)
    df["woy"] = np.minimum(((df["week_ending"].dt.day_of_year - 1) / 7.0).astype(int) + 1, 52).astype(float)
    df["hol"] = holiday_counts(df["week_ending"])
    df["hol_prev"] = pd.Series(df["hol"]).shift(1).fillna(0).values
    # flag of any input week that is flagged (used by the "without flagged weeks" variant)
    fl = df["flagged"]
    df["flag_any"] = ((fl + fl.shift(1).fillna(0) + fl.shift(2).fillna(0) + fl.shift(52).fillna(0)) > 0).astype(int)
    return df


def flag_any_h(df: pd.DataFrame, h: int) -> pd.Series:
    """1 if the target row or any attendance input used at horizon h (lag_h, lag_h+1, lag_52) is a flagged week."""
    fl = df["flagged"]
    return ((fl + fl.shift(h).fillna(0) + fl.shift(h + 1).fillna(0) + fl.shift(52).fillna(0)) > 0).astype(int)


# ------------------------------------------------------------------ models
class Standardise:
    def __init__(self):
        self.mu = self.sd = None

    def fit(self, X):
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0)
        self.sd[self.sd == 0] = 1.0
        return self

    def tf(self, X):
        return (X - self.mu) / self.sd


def _gam_terms(model: str, names: list[str]):
    from pygam import l, s
    terms = None
    for i, n in enumerate(names):
        if n == "woy":
            t = s(i, basis="cp", n_splines=10)
        elif n == "temp_mean":
            t = s(i, n_splines=8)
        else:
            t = l(i)
        terms = t if terms is None else terms + t
    return terms


class GAMModel:
    """pyGAM LinearGAM (identity link). M1 = autoregressive + calendar; M2 = M1 + weather terms."""

    def __init__(self, model: str, h: int, lam: float = 1.0):
        self.model, self.h, self.lam = model, h, lam
        self.names = feature_names(model, h)
        self.sc = Standardise()
        self.gam = None
        self.woy_i = self.names.index("woy")

    def _prep(self, X, fit=False):
        X = np.array(X, float)
        woy = X[:, self.woy_i].copy()
        if fit:
            self.sc.fit(X)
        Z = self.sc.tf(X)
        Z[:, self.woy_i] = woy      # keep raw 1..52 for the periodic spline
        return Z

    def tune(self, X, y):
        from pygam import LinearGAM
        Z = self._prep(X, fit=True)
        g = LinearGAM(_gam_terms(self.model, self.names))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g.gridsearch(Z, y / self.ymean(y), lam=np.logspace(-1, 3, 5), progress=False)
        self.lam = float(np.ravel(g.lam)[0])
        return self.lam

    @staticmethod
    def ymean(y):
        return float(np.mean(y))

    def fit(self, X, y):
        from pygam import LinearGAM
        Z = self._prep(X, fit=True)
        self.ym = self.ymean(y)
        self.gam = LinearGAM(_gam_terms(self.model, self.names), lam=self.lam, max_iter=200)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.gam.fit(Z, y / self.ym)
        return self

    def predict(self, X):
        return self.gam.predict(self._prep(X)) * self.ym

    def contributions(self, X_row, X_ref) -> dict:
        """Per-term effect (in attendances) of this row relative to the average row of X_ref.
        Used by the prototype to show the main drivers of a forecast (requirement R3)."""
        Z, Zr = self._prep(X_row), self._prep(X_ref)
        out = {}
        for i, n in enumerate(self.names):
            row = float(self.gam.partial_dependence(term=i, X=Z)[0])
            ref = float(np.mean(self.gam.partial_dependence(term=i, X=Zr)))
            out[n] = (row - ref) * self.ym
        return out


XGB_GRID = [dict(max_depth=2, n_estimators=200), dict(max_depth=3, n_estimators=200),
            dict(max_depth=2, n_estimators=500), dict(max_depth=3, n_estimators=400)]


class XGBModel:
    """XGBoost on the residual from the h-week persistence forecast: target = y - lag_h."""

    def __init__(self, model: str, h: int, params: dict | None = None, seed: int = 0):
        self.model, self.h, self.params, self.seed = model, h, params or XGB_GRID[0], seed
        self.names = feature_names(model, h)
        self.lag_i = self.names.index(f"lag_{h}")
        self.reg = None

    def _make(self, p):
        import xgboost as xgb
        return xgb.XGBRegressor(learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
                                min_child_weight=5, reg_lambda=5.0, n_jobs=1,
                                random_state=self.seed, verbosity=0, **p)

    def tune(self, X, y):
        """Time-series cross-validation inside the training window only."""
        X, y = np.array(X, float), np.array(y, float)
        n = len(y)
        folds = [(int(n * a), int(n * b)) for a, b in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0))]
        best, best_err = self.params, np.inf
        for p in XGB_GRID:
            errs = []
            for lo, hi in folds:
                m = self._make(p)
                m.fit(X[:lo], y[:lo] - X[:lo, self.lag_i])
                errs.append(np.mean(np.abs(m.predict(X[lo:hi]) + X[lo:hi, self.lag_i] - y[lo:hi])))
            e = float(np.mean(errs))
            if e < best_err:
                best, best_err = p, e
        self.params = best
        return best

    def fit(self, X, y):
        X, y = np.array(X, float), np.array(y, float)
        self.reg = self._make(self.params)
        self.reg.fit(X, y - X[:, self.lag_i])
        return self

    def predict(self, X):
        X = np.array(X, float)
        return self.reg.predict(X) + X[:, self.lag_i]


def make_model(name: str, h: int):
    if name in ("M1", "M2") or name in GROUPS:
        return GAMModel(name, h)
    if name in ("M3", "M3a"):
        return XGBModel(name, h)
    raise ValueError(name)


# ------------------------------------------------------------------ rolling-origin evaluation
def test_indices(df: pd.DataFrame, h: int) -> list[int]:
    """Indices of target weeks in the test period that have every input available."""
    ok = (df["week_ending"] >= TEST_START) & df["y"].notna() & df[f"lag_{h}"].notna() \
        & df[f"lag_{h + 1}"].notna() & df["lag_52"].notna()
    return list(np.where(ok)[0])


def rolling_forecasts(df: pd.DataFrame, model: str, h: int, exclude_flagged: bool = False,
                      seed: int = 0, test_df: pd.DataFrame | None = None,
                      test_rows: list[int] | None = None) -> pd.DataFrame:
    """Expanding-window rolling-origin forecasts of week t made at week t-h.

    The model is re-fitted at every origin on rows whose target was already observed at the origin.
    Hyper-parameters are re-tuned every RETUNE_EVERY origins using that window only.
    """
    names = feature_names(model, h)
    tests = test_rows if test_rows is not None else test_indices(df, h)
    pred_df = df if test_df is None else test_df      # features used at prediction time
    first_valid = int(np.where(df["lag_52"].notna() & df[f"lag_{h + 1}"].notna())[0][0])
    out, mdl = [], make_model(model, h)
    if isinstance(mdl, XGBModel):
        mdl.seed = seed
    for k, i in enumerate(tests):
        origin = i - h                       # last week whose attendance is known
        rows = np.arange(first_valid, origin + 1)
        tr = df.iloc[rows]
        if exclude_flagged:
            tr = tr[flag_any_h(df, h).loc[tr.index] == 0]
        tr = tr.dropna(subset=names + ["y"])
        X, y = tr[names].values, tr["y"].values
        if k % RETUNE_EVERY == 0:
            mdl.tune(X, y)
        mdl.fit(X, y)
        p = float(mdl.predict(pred_df.iloc[[i]][names].values)[0])
        out.append((df.at[i, "week_ending"], df.at[i, "y"], p))
    res = pd.DataFrame(out, columns=["week_ending", "actual", "forecast"])
    res["model"], res["h"] = model, h
    return res


def baseline_forecasts(df: pd.DataFrame, h: int) -> pd.DataFrame:
    idx = test_indices(df, h)
    sub = df.iloc[idx]
    b1 = pd.DataFrame({"week_ending": sub["week_ending"].values, "actual": sub["y"].values,
                       "forecast": sub["lag_52"].values, "model": "B1", "h": h})
    b2 = pd.DataFrame({"week_ending": sub["week_ending"].values, "actual": sub["y"].values,
                       "forecast": sub[f"lag_{h}"].values, "model": "B2", "h": h})
    return pd.concat([b1, b2], ignore_index=True)


# ------------------------------------------------------------------ metrics and tests
def mae(a, f):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(f))))


def mape(a, f):
    a = np.asarray(a, float)
    return float(np.mean(np.abs(a - np.asarray(f)) / a) * 100)


def rmse(a, f):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(f)) ** 2)))


def diebold_mariano(e1, e2, h: int = 1):
    """Two-sided DM test on absolute-error loss with the Harvey-Leybourne-Newbold small-sample
    correction. Returns (statistic, p, mean loss difference). d = |e1| - |e2|; negative d favours 1."""
    from scipy import stats
    d = np.abs(np.asarray(e1, float)) - np.abs(np.asarray(e2, float))
    n = len(d)
    dbar = d.mean()
    gamma0 = np.var(d, ddof=0)
    s = gamma0
    for k in range(1, h):
        gk = np.mean((d[k:] - dbar) * (d[:-k] - dbar))
        s += 2 * gk
    var = max(s, 1e-12) / n
    dm = dbar / np.sqrt(var)
    corr = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat = dm * corr
    p = 2 * stats.t.sf(abs(stat), df=n - 1)
    return float(stat), float(p), float(dbar)


def diebold_mariano_hac(e1, e2, h: int = 1, lags: int = 3):
    """Sensitivity variant: Newey-West (Bartlett) long-run variance of the loss differential with `lags` lags,
    same HLN scaling and t(n-1) reference. Use it to check that conclusions do not depend on ignoring autocorrelation."""
    from scipy import stats
    d = np.abs(np.asarray(e1, float)) - np.abs(np.asarray(e2, float))
    n = len(d)
    dbar = d.mean()
    s = np.var(d, ddof=0)
    for k in range(1, lags + 1):
        gk = np.mean((d[k:] - dbar) * (d[:-k] - dbar))
        s += 2 * (1 - k / (lags + 1)) * gk
    var = max(s, 1e-12) / n
    stat = dbar / np.sqrt(var) * np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    return float(stat), float(2 * stats.t.sf(abs(stat), df=n - 1)), float(dbar)


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj, running = {}, 0.0
    for rank, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - rank) * p))
        adj[k] = running
    return adj


# ------------------------------------------------------------------ alert logic (shared with the prototype)
def risk_thresholds(history) -> tuple[float, float]:
    """75th and 90th percentile of the previous 52 weeks of attendance (needs >= 52 values)."""
    h = np.asarray(history, float)[-52:]
    return float(np.percentile(h, 75)), float(np.percentile(h, 90))


def risk_class(forecast: float, history) -> str:
    p75, p90 = risk_thresholds(history)
    if forecast > p90:
        return "high"
    if forecast > p75:
        return "medium"
    return "low"
