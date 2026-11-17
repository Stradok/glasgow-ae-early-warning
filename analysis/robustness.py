"""Robustness checks for the weather effect (h = 1, all hospitals, same 146 test weeks).

  * Ablation by weather group: M1 + temperature only (M2t), + air quality only (M2a), + humidity/rain only (M2w).
  * Placebo: M2 fed LAST YEAR'S weather for the same week (shift 52). It keeps the season but removes the
    week-specific weather. If M2 only learned the season, the placebo would match M2.

    cd analysis && .venv/bin/python -I robustness.py
"""
import os
import sys

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forecast_lib as F  # noqa: E402

OUT = os.path.join(F.HERE, "results")


def run(site, model, placebo):
    df = F.build_features(site)
    if placebo:
        df = df.copy()
        for c in F.WEATHER_GAM:
            df[c] = df[c].shift(52)
    r = F.rolling_forecasts(df, model, 1)
    r["site"] = site
    if placebo:
        r["model"] = model + "_placebo"
    return r


def main():
    jobs = [(s, m, False) for s in F.SITES for m in ("M2t", "M2a", "M2w")] + [(s, "M2", True) for s in F.SITES]
    fc = pd.concat(Parallel(n_jobs=6)(delayed(run)(*j) for j in jobs), ignore_index=True)
    main_fc = pd.read_csv(os.path.join(OUT, "forecasts_long.csv"), parse_dates=["week_ending"])
    main_fc = main_fc[(main_fc.h == 1) & (main_fc.variant == "all") & main_fc.model.isin(["B2", "M1", "M2"])]
    fc["error"] = fc["actual"] - fc["forecast"]
    allfc = pd.concat([fc, main_fc[fc.columns]], ignore_index=True)
    allfc.to_csv(os.path.join(OUT, "robustness_forecasts.csv"), index=False)
    met = (allfc.groupby(["site", "model"]).apply(lambda g: pd.Series({
        "MAE": F.mae(g.actual, g.forecast), "MAPE": F.mape(g.actual, g.forecast)}), include_groups=False).reset_index())
    met.to_csv(os.path.join(OUT, "robustness_metrics.csv"), index=False)
    pairs = [("M2t", "M1"), ("M2a", "M1"), ("M2w", "M1"), ("M2", "M2_placebo"), ("M2_placebo", "M1"), ("M2", "M2t")]
    recs = []
    for s in F.SITES:
        piv = allfc[allfc.site == s].pivot(index="week_ending", columns="model", values="error")
        for a, b in pairs:
            stat, p, d = F.diebold_mariano(piv[a].values, piv[b].values, 1)
            recs.append(dict(site=s, model_a=a, model_b=b, mean_abs_err_diff=d, dm_stat=stat, p_raw=p))
    dm = pd.DataFrame(recs)
    dm["p_holm"] = np.nan
    for (a, b), g in dm[dm.site.isin(["QEUH", "GRI"])].groupby(["model_a", "model_b"]):
        adj = F.holm({r.site: r.p_raw for r in g.itertuples()})
        for i, r in g.iterrows():
            dm.loc[i, "p_holm"] = adj[r.site]
    dm.to_csv(os.path.join(OUT, "robustness_dm.csv"), index=False)
    pd.set_option("display.width", 200)
    print(met.pivot(index="model", columns="site", values="MAE").round(1))
    print(dm.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
