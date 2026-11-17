"""Check that the key numbers quoted in RESULTS.md match the CSV outputs.

    cd analysis && .venv/bin/python -I check_results.py
Exit code 1 if any number is missing or different.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results")
text = open(os.path.join(HERE, "RESULTS.md"), encoding="utf-8").read()
m = pd.read_csv(os.path.join(R, "metrics.csv"))
dm = pd.read_csv(os.path.join(R, "dm_tests.csv"))
rb = pd.read_csv(os.path.join(R, "robustness_metrics.csv"))
rd = pd.read_csv(os.path.join(R, "robustness_dm.csv"))
al = pd.read_csv(os.path.join(R, "alerts.csv"))
fm = pd.read_csv(os.path.join(R, "forecastwx_metrics.csv"))
fd = pd.read_csv(os.path.join(R, "forecastwx_dm.csv"))
te = pd.read_csv(os.path.join(R, "temperature_effect.csv")).set_index("site")

checks = []


def need(label, s):
    checks.append((label, s, s in text))


def mae(site, model, h=1, v="all"):
    return m[(m.site == site) & (m.model == model) & (m.h == h) & (m.variant == v)]["MAE"].iloc[0]


def skill(site, model):
    return 100 * m[(m.site == site) & (m.model == model) & (m.h == 1) & (m.variant == "all")]["skill_vs_B2"].iloc[0]


a = lambda s, mo, c: al[(al.site == s) & (al.model == mo)].iloc[0][c]


def dmrow(site, a, b, h=1, v="all"):
    return dm[(dm.site == site) & (dm.model_a == a) & (dm.model_b == b) & (dm.h == h) & (dm.variant == v)].iloc[0]


for s in ["QEUH", "GRI", "RHC"]:
    for model in ["B1", "B2", "M1", "M2", "M3", "M3a"]:
        need(f"MAE {model} {s}", f"{mae(s, model):.1f}")
for s, model in [("QEUH", "M2"), ("GRI", "M2"), ("RHC", "M2"), ("QEUH", "M1")]:
    need(f"skill {model} {s}", f"{skill(s, model):.1f}%")
for s in ["QEUH", "GRI"]:
    r = dmrow(s, "M2", "M1")
    need(f"H1 diff {s}", f"{r.mean_abs_err_diff:.1f}")
need("H1 reduction QEUH", f"{100 * (mae('QEUH', 'M1') - mae('QEUH', 'M2')) / mae('QEUH', 'M1'):.1f}%")
need("H1 reduction GRI", f"{100 * (mae('GRI', 'M1') - mae('GRI', 'M2')) / mae('GRI', 'M1'):.1f}%")
need("H1 GRI p", f"p = {dmrow('GRI', 'M2', 'M1').p_raw:.3f}")
need("H1 RHC p", f"p = {dmrow('RHC', 'M2', 'M1').p_raw:.3f}")
need("M3 vs M2 Holm p", f"p = {dmrow('QEUH', 'M3', 'M2').p_holm:.3f}")
need("M3 vs M3a p raw", f"p = {dmrow('QEUH', 'M3', 'M3a').p_raw:.3f}")
need("M3 vs M3a p holm", f"Holm {dmrow('QEUH', 'M3', 'M3a').p_holm:.3f}")
assert (dm[(dm.h == 1) & (dm.variant == "all") & (dm.model_a == "M2") & dm.model_b.isin(["B1", "B2"]) & dm.site.isin(["QEUH", "GRI"])]["p_holm"] < 0.001).all()

for model in ["M2_placebo", "M2a", "M2w", "M2t"]:
    for s in ["QEUH", "GRI", "RHC"]:
        need(f"ablation {model} {s}", f"{rb[(rb.site == s) & (rb.model == model)]['MAE'].iloc[0]:.1f}")
t = rd[(rd.site == "QEUH") & (rd.model_a == "M2") & (rd.model_b == "M2t")].iloc[0]
need("M2 vs M2t QEUH p", f"p = {t.p_raw:.3f}")
sub = rd[rd.site.isin(["QEUH", "GRI"]) & rd.model_a.isin(["M2a", "M2w"]) & (rd.model_b == "M1")]
assert (sub.p_raw > 0.4).all(), "claim 'all p > 0.4' is false"
for s in ["QEUH", "GRI", "RHC"]:
    need(f"partial effect {s}", f"{int(te.loc[s, 'partial_effect'])} ")
    need(f"partial pct {s}", f"{te.loc[s, 'partial_pct']:.1f}%")
need("total effect QEUH", f"{int(te.loc['QEUH', 'total_effect'])} at QEUH ({te.loc['QEUH', 'total_pct']:.1f}%)")
need("total effect GRI", f"{int(te.loc['GRI', 'total_effect'])} at GRI ({te.loc['GRI', 'total_pct']:.1f}%)")
need("total effect RHC", f"{int(te.loc['RHC', 'total_effect'])} at RHC".replace("-", "-"))
need("per degree QEUH", f"{te.loc['QEUH', 'per_degree_rise']:.1f} more attendances at QEUH")
need("per degree GRI", f"{te.loc['GRI', 'per_degree_rise']:.1f} at GRI")
need("t5", f"{te.loc['QEUH', 't5']:.1f} to {te.loc['QEUH', 't95']:.1f} °C")
for s in ["QEUH", "GRI", "RHC"]:
    need(f"noflag M2 {s}", f"{mae(s, 'M2', 1, 'noflag'):.1f}")
    need(f"noflag M1 {s}", f"{mae(s, 'M1', 1, 'noflag'):.1f}")
r = dmrow("QEUH", "M2", "M1", 4, "noflag")
need("noflag h4 Holm", f"Holm p = {r.p_holm:.3f}")
hac = pd.read_csv(os.path.join(R, "dm_hac.csv"))
hg = hac[(hac.site == "GRI") & (hac.model_a == "M2") & (hac.model_b == "M1")].set_index("lags")["p_raw"]
need("HAC GRI", f"p = {hg[3]:.3f} and {hg[8]:.3f}")
hq = hac[(hac.site == "QEUH") & (hac.model_a == "M2") & (hac.model_b == "M1")].set_index("lags")["p_holm"]
need("HAC QEUH", f"Holm p = {hq[3]:.3f} and {hq[8]:.3f}")
d2 = dmrow("QEUH", "M3", "M2", 2)
need("M3 vs M2 h2", f"raw p = {d2.p_raw:.3f}, Holm {d2.p_holm:.3f}")
need("M3 vs M2 h2 MAE", f"{mae('QEUH', 'M3', 2):.1f} vs {mae('QEUH', 'M2', 2):.1f}")
need("alert QEUH ci", f"precision {a('QEUH', 'M2', 'precision'):.2f} (95% interval {a('QEUH', 'M2', 'precision_lo'):.2f} to {a('QEUH', 'M2', 'precision_hi'):.2f})")
need("alert QEUH rec ci", f"recall {a('QEUH', 'M2', 'recall'):.2f} ({a('QEUH', 'M2', 'recall_lo'):.2f} to {a('QEUH', 'M2', 'recall_hi'):.2f})")
need("alert RHC", f"precision {a('RHC', 'M2', 'precision'):.2f} and recall {a('RHC', 'M2', 'recall'):.2f}, against {a('RHC', 'B2', 'precision'):.2f} and {a('RHC', 'B2', 'recall'):.2f}")
for h in (2, 4):
    assert dmrow("QEUH", "M2", "M1", h).p_holm < 0.0025 and dmrow("GRI", "M2", "M1", h).p_holm > 0.05
need("horizon holm", f"{dmrow('QEUH', 'M2', 'M1', 2).p_holm:.3f}")
need("alert QEUH M2 alerts", f"raises {int(a('QEUH', 'M2', 'alerts'))} alerts for {int(a('QEUH', 'M2', 'actual_high'))} high weeks")
need("alert QEUH M2 precision", f"precision {a('QEUH', 'M2', 'precision'):.2f}")
need("alert QEUH M2 fa", f"{a('QEUH', 'M2', 'false_alarms_per_month'):.2f} false alarms")
need("alert QEUH M2 recall", f"recall {a('QEUH', 'M2', 'recall'):.2f}")
need("alert QEUH B2 recall", f"recall {a('QEUH', 'B2', 'recall'):.2f}")
need("alert QEUH B2 precision", f"precision {a('QEUH', 'B2', 'precision'):.2f}")
need("alert QEUH B2 fa", f"{a('QEUH', 'B2', 'false_alarms_per_month'):.2f} false alarms")
need("alert GRI M2", f"precision {a('GRI', 'M2', 'precision'):.2f} and recall {a('GRI', 'M2', 'recall'):.2f}")
n = int(fm.groupby("site")["n"].first().iloc[0])
need("forecastwx weeks", f"{n} of the 146")
fx = lambda s, mo: fm[(fm.site == s) & (fm.model == mo)].iloc[0]
for s in ["QEUH", "GRI", "RHC"]:
    for mo in ["M1", "M2_nowcast", "M2_forecastwx", "M2t_forecastwx"]:
        need(f"fwx {mo} {s}", f"{fx(s, mo)['MAE']:.1f}")
need("fwx skill QEUH", f"{100 * fx('QEUH', 'M2_forecastwx')['skill_vs_B2']:.1f}%")
need("fwx skill GRI", f"{100 * fx('GRI', 'M2_forecastwx')['skill_vs_B2']:.1f}%")
g = lambda s, a_, b_: fd[(fd.site == s) & (fd.model_a == a_) & (fd.model_b == b_)].iloc[0]
need("fwx GRI M2f vs M1 p", f"p = {g('GRI', 'M2_forecastwx', 'M1').p_raw:.3f}")
need("fwx GRI loss holm", f"p = {g('GRI', 'M2_forecastwx', 'M2_nowcast').p_holm:.3f}")
assert g("QEUH", "M2_forecastwx", "M1").p_holm < 0.001
# weekly temperature forecast quality
sys.path.insert(0, HERE)
import forecast_lib as F  # noqa: E402
import forecast_weather_test as W  # noqa: E402
import json  # noqa: E402
df = F.build_features("QEUH")
fw = W.weekly_forecast_features(json.load(open(W.CACHE)), df)
rows = [i for i in F.test_indices(df, 1) if df.at[i, "week_ending"] in fw.index]
obs = df.iloc[rows]["temp_mean"].values
fc = fw.loc[df.iloc[rows]["week_ending"].values, "temp_mean"].values
need("temp RMSE", f"RMSE {np.sqrt(np.mean((fc - obs) ** 2)):.2f}")
need("temp bias", f"bias {np.mean(fc - obs):+.2f}")
hot, cold = F.daily_weather_counts(df[["week_ending"]]).attrs["hot_thr"], F.daily_weather_counts(df[["week_ending"]]).attrs["cold_thr"]
need("hot thr", f"{hot:.1f} °C")
need("cold thr", f"{cold:.1f} °C")

# Section 5b: alerts for M2t, forecast weather and the medium tier (results/alerts_extended.csv)
ae = pd.read_csv(os.path.join(R, "alerts_extended.csv"))


def ext(src, tier, site, model):
    r = ae[(ae.source == src) & (ae.tier == tier) & (ae.site == site) & (ae.model == model)].iloc[0]
    return (f"{site} precision {r.precision:.2f} ({r.precision_lo:.2f} to {r.precision_hi:.2f}), recall {r.recall:.2f} "
            f"({r.recall_lo:.2f} to {r.recall_hi:.2f}), {r.false_alarms_per_month:.2f} false alarms a month")


for src in ("observed", "forecast"):
    for site in ("QEUH", "GRI", "RHC"):
        need(f"5b high M2t {src} {site}", ext(src, "high", site, "M2t"))
need("5b QEUH persistence", ext("forecast", "high", "QEUH", "B2").replace("QEUH ", ""))
need("5b GRI persistence", ext("forecast", "high", "GRI", "B2").replace("GRI ", ""))
need("5b medium QEUH M2t", ext("observed", "medium", "QEUH", "M2t"))
need("5b medium QEUH persistence", ext("observed", "medium", "QEUH", "B2").replace("QEUH ", ""))
for tier in ("high", "medium"):
    need(f"5b base rates {tier}", ", ".join(
        f"{s} {100 * ae[(ae.source == 'observed') & (ae.tier == tier) & (ae.site == s) & (ae.model == 'B2')].iloc[0].base_rate:.1f}%"
        for s in ("QEUH", "GRI", "RHC")))
# the "11 to 26 alerts" and "2.5 to 4.5 times" statements
hi = ae[(ae.tier == "high") & (ae.model == "M2t") & (ae.site.isin(["QEUH", "GRI"]))]
assert hi.alerts.min() == 11 and hi.alerts.max() == 26, (hi.alerts.min(), hi.alerts.max())
ratio = hi.precision / hi.base_rate
assert 2.3 < ratio.min() and ratio.max() < 4.6, (ratio.min(), ratio.max())
assert 0.33 - 5e-3 <= hi.recall.min() and hi.recall.max() <= 0.46 + 5e-3

bad = [c for c in checks if not c[2]]
for label, s, ok in checks:
    print("OK  " if ok else "MISSING", label, "->", s)
print(f"\n{len(checks) - len(bad)} / {len(checks)} numbers confirmed")
sys.exit(1 if bad else 0)
