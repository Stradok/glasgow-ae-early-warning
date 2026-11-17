"""Run the full rolling-origin evaluation (report Sections 3.2.2-3.2.3).

    cd analysis && .venv/bin/python -I run_experiments.py

Writes results/forecasts_long.csv, metrics.csv, dm_tests.csv, alerts.csv.
Runtime: a few minutes on a laptop (weekly re-fit of every model at every origin).
XGBoost forecasts are the mean of SEEDS random seeds (bagging over seeds) to remove seed noise.
"""
import os
import sys
import time

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forecast_lib as F  # noqa: E402

OUT = os.path.join(F.HERE, "results")
SEEDS = [0, 1, 2]
HORIZONS = [1, 2, 4]
MODELS = ["M1", "M2", "M3", "M3a"]


def task(site, model, h, variant):
    df = F.build_features(site)
    excl = variant == "noflag"
    if model in ("M3", "M3a"):
        runs = [F.rolling_forecasts(df, model, h, excl, seed=s) for s in SEEDS]
        r = runs[0].copy()
        r["forecast"] = np.mean([x["forecast"].values for x in runs], axis=0)
    else:
        r = F.rolling_forecasts(df, model, h, excl)
    r["site"], r["variant"] = site, variant
    return r


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    jobs = [(s, m, h, v) for s in F.SITES for m in MODELS for h in HORIZONS for v in ("all", "noflag")]
    parts = Parallel(n_jobs=min(11, os.cpu_count() or 2))(delayed(task)(*j) for j in jobs)
    fc = pd.concat(parts, ignore_index=True)
    # baselines do not depend on the training window: copy to both variants
    base = []
    for s in F.SITES:
        df = F.build_features(s)
        for h in HORIZONS:
            b = F.baseline_forecasts(df, h)
            b["site"] = s
            for v in ("all", "noflag"):
                x = b.copy()
                x["variant"] = v
                base.append(x)
    fc = pd.concat([fc] + base, ignore_index=True)
    fc["error"] = fc["actual"] - fc["forecast"]
    fc.to_csv(os.path.join(OUT, "forecasts_long.csv"), index=False)
    print(f"forecasts: {len(fc)} rows in {time.time() - t0:.0f}s")

    # ---------------- metrics
    rows = []
    for (s, h, v, m), g in fc.groupby(["site", "h", "variant", "model"]):
        rows.append(dict(site=s, h=h, variant=v, model=m, n=len(g),
                         MAE=F.mae(g.actual, g.forecast), MAPE=F.mape(g.actual, g.forecast),
                         RMSE=F.rmse(g.actual, g.forecast)))
    met = pd.DataFrame(rows)
    ref = met[met.model == "B2"].set_index(["site", "h", "variant"])["MAE"]
    ref1 = met[met.model == "B1"].set_index(["site", "h", "variant"])["MAE"]
    met["skill_vs_B2"] = [1 - r.MAE / ref[(r.site, r.h, r.variant)] for r in met.itertuples()]
    met["skill_vs_B1"] = [1 - r.MAE / ref1[(r.site, r.h, r.variant)] for r in met.itertuples()]
    met.to_csv(os.path.join(OUT, "metrics.csv"), index=False)

    # ---------------- Diebold-Mariano tests (absolute-error loss)
    pairs = [("M2", "M1"), ("M2", "B1"), ("M2", "B2"), ("M1", "B2"), ("M3", "B2"),
             ("M3", "M3a"), ("M3", "M2"), ("M3a", "M1")]
    recs = []
    for s in F.SITES:
        for h in HORIZONS:
            for v in ("all", "noflag"):
                sub = fc[(fc.site == s) & (fc.h == h) & (fc.variant == v)]
                piv = sub.pivot(index="week_ending", columns="model", values="error")
                for a, b in pairs:
                    stat, p, d = F.diebold_mariano(piv[a].values, piv[b].values, h)
                    recs.append(dict(site=s, h=h, variant=v, model_a=a, model_b=b, dm_stat=stat,
                                     p_raw=p, mean_abs_err_diff=d,
                                     better="A" if d < 0 else "B"))
    dm = pd.DataFrame(recs)
    # Holm across the two adult hospitals, per comparison / horizon / variant (RHC is exploratory)
    dm["p_holm"] = np.nan
    for (h, v, a, b), g in dm[dm.site.isin(["QEUH", "GRI"])].groupby(["h", "variant", "model_a", "model_b"]):
        adj = F.holm({r.site: r.p_raw for r in g.itertuples()})
        for idx, r in g.iterrows():
            dm.loc[idx, "p_holm"] = adj[r.site]
    dm.to_csv(os.path.join(OUT, "dm_tests.csv"), index=False)

    # ---------------- sensitivity: Newey-West (HAC) variance for the primary comparisons (h = 1)
    recs = []
    for s in F.SITES:
        piv = fc[(fc.site == s) & (fc.h == 1) & (fc.variant == "all")].pivot(index="week_ending", columns="model", values="error")
        for a_, b_ in (("M2", "M1"), ("M2", "B2"), ("M2", "B1")):
            for lags in (3, 8):
                stat, p, d = F.diebold_mariano_hac(piv[a_].values, piv[b_].values, 1, lags)
                recs.append(dict(site=s, model_a=a_, model_b=b_, lags=lags, mean_abs_err_diff=d, dm_stat=stat, p_raw=p))
    hac = pd.DataFrame(recs)
    hac["p_holm"] = np.nan
    for (a_, b_, lg), g in hac[hac.site.isin(["QEUH", "GRI"])].groupby(["model_a", "model_b", "lags"]):
        adj = F.holm({r.site: r.p_raw for r in g.itertuples()})
        for i, r in g.iterrows():
            hac.loc[i, "p_holm"] = adj[r.site]
    hac.to_csv(os.path.join(OUT, "dm_hac.csv"), index=False)

    # ---------------- alert metrics (h = 1, variant all)
    recs = []
    for s in F.SITES:
        df = F.build_features(s).set_index("week_ending")
        sub = fc[(fc.site == s) & (fc.h == 1) & (fc.variant == "all")]
        for m, g in sub.groupby("model"):
            tp = fp = fn = tn = 0
            for r in g.itertuples():
                pos = df.index.get_loc(r.week_ending)
                hist = df["y"].iloc[pos - 52:pos].values        # previous 52 weeks, known at forecast time
                thr = float(np.percentile(hist, 90))
                pred, act = r.forecast > thr, r.actual > thr
                tp += pred and act
                fp += pred and not act
                fn += (not pred) and act
                tn += (not pred) and not act
            months = len(g) / 4.345
            def wilson(k, n, z=1.96):
                if n == 0:
                    return (np.nan, np.nan)
                ph = k / n
                den = 1 + z * z / n
                c = (ph + z * z / (2 * n)) / den
                hw = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
                return (c - hw, c + hw)
            plo, phi = wilson(tp, tp + fp)
            rlo, rhi = wilson(tp, tp + fn)
            recs.append(dict(site=s, model=m, weeks=len(g), actual_high=tp + fn, alerts=tp + fp, TP=tp, FP=fp, FN=fn,
                             precision=tp / (tp + fp) if tp + fp else np.nan,
                             recall=tp / (tp + fn) if tp + fn else np.nan,
                             precision_lo=plo, precision_hi=phi, recall_lo=rlo, recall_hi=rhi,
                             false_alarms_per_month=fp / months))
    pd.DataFrame(recs).to_csv(os.path.join(OUT, "alerts.csv"), index=False)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
