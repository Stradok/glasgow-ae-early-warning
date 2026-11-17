"""Alert evaluation for the models and tiers the prototype actually uses.

run_experiments.py evaluated "high" alerts only for the pre-specified models with observed weather. The prototype uses
the temperature-only model M2t, runs on forecast weather, and shows a "medium" tier. This script evaluates those with the
SAME rule, from forecasts that already exist (no model is re-fitted):
  * source "observed":  results/forecasts_long.csv (variant all, h=1) plus results/robustness_forecasts.csv (M2t), 146 weeks
  * source "forecast":  results/forecastwx_forecasts.csv (models trained on reanalysis, tested on archived ECMWF forecasts), 135 weeks
Tiers (thresholds = percentiles of the previous 52 weeks, known at forecast time, as in forecast_lib.risk_class):
  high   : alert when forecast > 90th percentile; positive when actual > 90th percentile
  medium : alert when forecast > 75th percentile; positive when actual > 75th percentile  ("medium or above")
Also reports the base rate (share of positive weeks), the precision a random alert would have.

    cd analysis && .venv/bin/python -I alerts_eval.py     -> results/alerts_extended.csv
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forecast_lib as F  # noqa: E402

OUT = os.path.join(F.HERE, "results")
PCT = {"high": 90, "medium": 75}
# model names differ by source: the forecast-weather file labels how the weather was supplied
MODELS = {"observed": {"B2": "B2", "M1": "M1", "M2": "M2", "M2t": "M2t"},
          "forecast": {"B2": "B2", "M1": "M1", "M2": "M2_forecastwx", "M2t": "M2t_forecastwx"}}


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    hw = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (c - hw, c + hw)


def load_sources() -> dict[str, pd.DataFrame]:
    main = pd.read_csv(os.path.join(OUT, "forecasts_long.csv"), parse_dates=["week_ending"])
    main = main[(main.h == 1) & (main.variant == "all")]
    rob = pd.read_csv(os.path.join(OUT, "robustness_forecasts.csv"), parse_dates=["week_ending"])
    rob = rob[(rob.h == 1) & (rob.model == "M2t")]
    obs = pd.concat([main, rob[main.columns.intersection(rob.columns)]], ignore_index=True)
    fw = pd.read_csv(os.path.join(OUT, "forecastwx_forecasts.csv"), parse_dates=["week_ending"])
    fw = fw[fw.h == 1]
    return {"observed": obs, "forecast": fw}


def evaluate() -> pd.DataFrame:
    recs = []
    for source, fc in load_sources().items():
        for s in F.SITES:
            df = F.build_features(s).set_index("week_ending")
            for m, name in MODELS[source].items():
                g = fc[(fc.site == s) & (fc.model == name)].sort_values("week_ending")
                if g.empty:
                    continue
                for tier, pct in PCT.items():
                    tp = fp = fn = tn = 0
                    for r in g.itertuples():
                        pos = df.index.get_loc(r.week_ending)
                        thr = float(np.percentile(df["y"].iloc[pos - 52:pos].values, pct))   # known at forecast time
                        pred, act = r.forecast > thr, r.actual > thr
                        tp += pred and act
                        fp += pred and not act
                        fn += (not pred) and act
                        tn += (not pred) and not act
                    n_alert, n_pos, months = tp + fp, tp + fn, len(g) / 4.345
                    plo, phi = wilson(tp, n_alert)
                    rlo, rhi = wilson(tp, n_pos)
                    recs.append(dict(source=source, tier=tier, site=s, model=m, weeks=len(g), actual_pos=n_pos,
                                     base_rate=n_pos / len(g), alerts=n_alert, TP=tp, FP=fp, FN=fn,
                                     precision=tp / n_alert if n_alert else np.nan,
                                     recall=tp / n_pos if n_pos else np.nan,
                                     precision_lo=plo, precision_hi=phi, recall_lo=rlo, recall_hi=rhi,
                                     false_alarms_per_month=fp / months))
    return pd.DataFrame(recs)


def main():
    res = evaluate()
    res.to_csv(os.path.join(OUT, "alerts_extended.csv"), index=False)
    pd.set_option("display.width", 200)
    cols = ["source", "tier", "site", "model", "weeks", "actual_pos", "alerts", "TP", "precision", "precision_lo",
            "precision_hi", "recall", "recall_lo", "recall_hi", "false_alarms_per_month"]
    print(res[res.model.isin(["B2", "M2", "M2t"])][cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
