"""Figures for the report (written to analysis/figures/). Run after run_experiments.py and robustness.py.

    cd analysis && .venv/bin/python -I make_figures.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forecast_lib as F  # noqa: E402

OUT = os.path.join(F.HERE, "figures")
RES = os.path.join(F.HERE, "results")
os.makedirs(OUT, exist_ok=True)
# Okabe-Ito colour-blind-safe palette
C = {"B2": "#999999", "B1": "#CCCCCC", "M1": "#56B4E9", "M2": "#0072B2", "M3": "#D55E00", "M3a": "#E69F00",
     "obs": "#222222"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 130})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print("wrote", name)


def fig_data_overview():
    w = F.load_weekly()
    fig, ax = plt.subplots(2, 1, figsize=(7.5, 5), sharex=True)
    for s, col in zip(F.SITES, ["#0072B2", "#D55E00", "#009E73"]):
        y = w[f"att_{s}"]
        ax[0].plot(w.week_ending, y, lw=0.8, color=col, label=s)
        flagged = y < 0.6 * y.median()
        ax[0].scatter(w.week_ending[flagged], y[flagged], s=8, color=col, zorder=3)
    ax[0].set_ylabel("unplanned attendances / week")
    ax[0].legend(frameon=False, ncol=3, loc="lower right")
    ax[0].set_title("Weekly attendance (dots: weeks below 60% of the site median)", fontsize=9, loc="left")
    ax[1].plot(w.week_ending, w.temp_mean, lw=0.8, color="#444444")
    ax[1].set_ylabel("weekly mean temperature (°C)")
    ax[1].set_title("Glasgow weather (ERA5-Land reanalysis)", fontsize=9, loc="left")
    save(fig, "fig_data_overview.png")


def fig_forecasts():
    fc = pd.read_csv(os.path.join(RES, "forecasts_long.csv"), parse_dates=["week_ending"])
    fig, axes = plt.subplots(3, 1, figsize=(7.5, 7), sharex=True)
    for ax, s in zip(axes, F.SITES):
        g = fc[(fc.site == s) & (fc.h == 1) & (fc.variant == "all")]
        a = g[g.model == "M2"]
        ax.plot(a.week_ending, a.actual, color=C["obs"], lw=1.2, label="actual")
        for m, ls in (("B2", ":"), ("M1", "-"), ("M2", "-")):
            x = g[g.model == m]
            ax.plot(x.week_ending, x.forecast, color=C[m], lw=1.0, ls=ls,
                    label={"B2": "last week (B2)", "M1": "M1 no weather", "M2": "M2 with weather"}[m])
        ax.set_title(s, loc="left", fontsize=9)
        ax.set_ylabel("attendances / week")
    axes[0].legend(frameon=False, ncol=4, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, 1.35))
    save(fig, "fig_forecasts.png")


def fig_mae():
    m = pd.read_csv(os.path.join(RES, "metrics.csv"))
    m = m[(m.h == 1) & (m.variant == "all")]
    models = ["B1", "B2", "M1", "M2", "M3"]
    names = {"B1": "B1 seasonal", "B2": "B2 last week", "M1": "M1 GAM", "M2": "M2 GAM+weather", "M3": "M3 XGBoost"}
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    w = 0.16
    for k, mod in enumerate(models):
        v = [m[(m.site == s) & (m.model == mod)]["MAE"].iloc[0] for s in F.SITES]
        bars = ax.bar(np.arange(3) + (k - 2) * w, v, w, color=C[mod], label=names[mod])
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{b.get_height():.0f}", ha="center", fontsize=6)
    ax.set_xticks(range(3))
    ax.set_xticklabels(F.SITES)
    ax.set_ylabel("mean absolute error (attendances / week)")
    ax.legend(frameon=False, fontsize=7, ncol=3)
    ax.set_ylim(0, 125)
    save(fig, "fig_mae.png")


def fig_horizon():
    m = pd.read_csv(os.path.join(RES, "metrics.csv"))
    m = m[m.variant == "all"]
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.8), sharey=False)
    for ax, s in zip(axes, F.SITES):
        for mod, ls in (("B2", ":"), ("M1", "-"), ("M2", "-"), ("M3", "-")):
            g = m[(m.site == s) & (m.model == mod)].sort_values("h")
            ax.plot(g.h, g.MAE, marker="o", ms=3, color=C[mod], ls=ls, label=mod)
        ax.set_title(s, fontsize=9, loc="left")
        ax.set_xticks([1, 2, 4])
        ax.set_xlabel("weeks ahead")
    axes[0].set_ylabel("MAE")
    axes[0].legend(frameon=False, fontsize=7)
    save(fig, "fig_horizon.png")


def fig_robustness():
    r = pd.read_csv(os.path.join(RES, "robustness_metrics.csv"))
    order = ["B2", "M1", "M2_placebo", "M2a", "M2w", "M2t", "M2"]
    lab = {"B2": "last week", "M1": "M1 (no weather)", "M2_placebo": "M2 with last year's weather",
           "M2a": "M1 + air quality", "M2w": "M1 + humidity, rain", "M2t": "M1 + temperature", "M2": "M2 (all weather)"}
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    w = 0.26
    for k, s in enumerate(F.SITES):
        v = [r[(r.site == s) & (r.model == m)]["MAE"].iloc[0] for m in order]
        ax.barh(np.arange(len(order)) + (k - 1) * w, v, w, label=s, color=["#0072B2", "#D55E00", "#009E73"][k])
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([lab[m] for m in order], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("MAE (attendances / week), one week ahead")
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    save(fig, "fig_robustness.png")


def fig_temperature_effect():
    from pygam import LinearGAM  # noqa: F401
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.8))
    for ax, s in zip(axes, F.SITES):
        df = F.build_features(s)
        names = F.feature_names("M2t", 1)
        tr = df.dropna(subset=names + ["y"])
        tr = tr[F.flag_any_h(df, 1).loc[tr.index] == 0]
        m = F.make_model("M2t", 1)
        m.tune(tr[names].values, tr["y"].values)
        m.fit(tr[names].values, tr["y"].values)
        i = names.index("temp_mean")
        XX = m.gam.generate_X_grid(term=i, n=100)
        pdp, conf = m.gam.partial_dependence(term=i, X=XX, width=0.95)
        temp = XX[:, i] * m.sc.sd[i] + m.sc.mu[i]
        centre = float(np.mean(m.gam.partial_dependence(term=i, X=m._prep(tr[names].values))))  # zero = average week
        ax.plot(temp, (pdp - centre) * m.ym, color="#0072B2")
        ax.fill_between(temp, (conf[:, 0] - centre) * m.ym, (conf[:, 1] - centre) * m.ym, alpha=0.2, color="#0072B2")
        ax.axhline(0, color="#999", lw=0.6)
        ax.set_title(s, fontsize=9, loc="left")
        ax.set_xlabel("weekly mean temperature (°C)")
    axes[0].set_ylabel("effect of this week's temperature\n(last week's held fixed)")
    save(fig, "fig_temperature_effect.png")


def temperature_effect_table():
    """Size of the temperature association from the fitted M2t GAM (writes results/temperature_effect.csv).

    partial = this week's temperature moves from the 5th to the 95th percentile, last week's temperature held at its
              average (the plotted s(temp_mean) term).
    total   = this week's and last week's temperature move together (a sustained warm week compared with a
              sustained cold one); other inputs at their training mean. They differ because the model also uses
              the week-to-week CHANGE in temperature."""
    rows = []
    for s in F.SITES:
        df = F.build_features(s)
        names = F.feature_names("M2t", 1)
        tr = df.dropna(subset=names + ["y"])
        tr = tr[F.flag_any_h(df, 1).loc[tr.index] == 0]
        m = F.make_model("M2t", 1)
        m.tune(tr[names].values, tr["y"].values)
        m.fit(tr[names].values, tr["y"].values)
        t5, t95 = np.percentile(tr["temp_mean"], [5, 95])
        ref = tr[names].mean().values.reshape(1, -1)

        def pred(this_t, last_t, ref=ref, m=m, names=names):
            x = ref.copy()
            x[0, names.index("temp_mean")] = this_t
            x[0, names.index("temp_mean_l1")] = last_t
            x[0, names.index("woy")] = 26.0
            return float(m.predict(x)[0])
        mean_last = float(tr["temp_mean_l1"].mean())
        partial = pred(t95, mean_last) - pred(t5, mean_last)
        total = pred(t95, t95) - pred(t5, t5)
        mid = float(np.median(tr["temp_mean"]))
        per_deg = pred(mid + 1, mid) - pred(mid, mid)        # one degree warmer than last week
        mean_att = float(tr["y"].mean())
        rows.append(dict(site=s, t5=round(t5, 1), t95=round(t95, 1), partial_effect=round(partial),
                         total_effect=round(total), mean_att=round(mean_att),
                         partial_pct=round(100 * partial / mean_att, 1), total_pct=round(100 * total / mean_att, 1),
                         per_degree_rise=round(per_deg, 1)))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "temperature_effect.csv"), index=False)
    print(out.to_string(index=False))


def fig_importance():
    """Permutation importance for XGBoost (M3): trained before 2024, MAE increase when a feature is shuffled in the test set."""
    rng = np.random.default_rng(0)
    names = F.feature_names("M3", 1)
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.4), sharex=False)
    rows = []
    for ax, s in zip(axes, ["QEUH", "GRI"]):
        df = F.build_features(s)
        tests = F.test_indices(df, 1)
        first = int(np.where(df["lag_52"].notna())[0][0])
        tr = df.iloc[first:tests[0]].dropna(subset=names + ["y"])
        te = df.iloc[tests]
        mdl = F.make_model("M3", 1)
        mdl.tune(tr[names].values, tr["y"].values)
        mdl.fit(tr[names].values, tr["y"].values)
        Xte, yte = te[names].values.copy(), te["y"].values
        base = F.mae(yte, mdl.predict(Xte))
        imp = {}
        for j, n in enumerate(names):
            inc = []
            for _ in range(20):
                Xp = Xte.copy()
                Xp[:, j] = rng.permutation(Xp[:, j])
                inc.append(F.mae(yte, mdl.predict(Xp)) - base)
            imp[n] = float(np.mean(inc))
        top = sorted(imp.items(), key=lambda kv: -kv[1])[:10]
        ax.barh([k for k, _ in top][::-1], [v for _, v in top][::-1], color="#D55E00")
        ax.set_title(f"{s} (base MAE {base:.0f})", fontsize=9, loc="left")
        ax.set_xlabel("MAE increase when shuffled")
        ax.tick_params(axis="y", labelsize=7)
        rows += [dict(site=s, feature=k, mae_increase=v) for k, v in sorted(imp.items(), key=lambda kv: -kv[1])]
    pd.DataFrame(rows).to_csv(os.path.join(RES, "xgb_permutation_importance.csv"), index=False)
    save(fig, "fig_importance.png")


if __name__ == "__main__":
    fig_data_overview()
    fig_forecasts()
    fig_mae()
    fig_horizon()
    fig_robustness()
    fig_temperature_effect()
    temperature_effect_table()
    fig_importance()
