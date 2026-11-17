import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import forecast_lib as F  # noqa: E402


def test_holm_adjusts_in_rank_order():
    adj = F.holm({"a": 0.01, "b": 0.04})
    assert adj["a"] == pytest.approx(0.02) and adj["b"] == pytest.approx(0.04)
    # monotone: adjusted p never decreases with rank, and never exceeds 1
    adj = F.holm({"a": 0.30, "b": 0.20, "c": 0.90})
    assert max(adj.values()) <= 1.0 and adj["b"] <= adj["a"] <= adj["c"]


def test_diebold_mariano_sign_and_identical_errors():
    rng = np.random.default_rng(1)
    e_bad = rng.normal(0, 10, 150)
    e_good = e_bad * 0.5                       # model 1 has smaller errors everywhere
    stat, p, d = F.diebold_mariano(e_good, e_bad)
    assert d < 0 and stat < 0 and p < 0.001    # negative = first model better
    stat, p, d = F.diebold_mariano(e_bad, e_bad)
    assert d == 0 and p == pytest.approx(1.0)


def test_diebold_mariano_matches_hand_calculation():
    e1, e2 = np.array([1., 2, 3, 4, 5, 6]), np.array([2., 1, 5, 3, 8, 6])
    d = np.abs(e1) - np.abs(e2)
    n = len(d)
    dm = d.mean() / np.sqrt(np.var(d) / n)
    expected = dm * np.sqrt((n + 1 - 2) / n)
    stat, _, _ = F.diebold_mariano(e1, e2, 1)
    assert stat == pytest.approx(expected)


def test_risk_class_uses_previous_52_weeks():
    hist = np.arange(1, 101)                  # last 52 weeks are 49..100
    p75, p90 = F.risk_thresholds(hist)
    assert p75 == pytest.approx(np.percentile(np.arange(49, 101), 75))
    assert F.risk_class(p90 + 1, hist) == "high"
    assert F.risk_class((p75 + p90) / 2, hist) == "medium"
    assert F.risk_class(p75 - 1, hist) == "low"


def test_feature_alignment_and_test_set_size():
    df = F.build_features("QEUH")
    i = 300
    assert df.at[i, "lag_1"] == df.at[i - 1, "y"]
    assert df.at[i, "lag_52"] == df.at[i - 52, "y"]
    assert df.at[i, "temp_mean_l1"] == df.at[i - 1, "temp_mean"]
    assert len(F.test_indices(df, 1)) == 146            # same test weeks as the interim baselines
    assert (df["week_ending"].dt.weekday == 6).all()    # weeks end on Sunday


@pytest.mark.parametrize("h", [1, 2, 4])
@pytest.mark.parametrize("model", ["M1", "M2", "M3"])
def test_no_leakage_from_the_future(model, h):
    """The forecast for week i made at origin i-h must not change if ALL attendance after the origin and ALL
    weather after the target week are scrambled (the target week's own weather is allowed: documented nowcast)."""
    weekly = F.load_weekly()
    df = F.build_features("QEUH", weekly)
    i = F.test_indices(df, h)[10]
    base = F.rolling_forecasts(df, model, h, test_rows=[i])["forecast"].iloc[0]
    w2 = weekly.copy()
    for c in w2.columns[1:]:
        w2[c] = w2[c].astype(float)
    rng = np.random.default_rng(0)
    w2.loc[i - h + 1:, "att_QEUH"] = rng.integers(500, 3000, len(w2) - (i - h + 1))
    for c in ("temp_mean", "temp_max", "temp_min", "humidity_mean", "precip_sum", "pm2_5_mean", "pm10_mean"):
        w2.loc[i + 1:, c] = rng.normal(10, 5, len(w2) - (i + 1))
    again = F.rolling_forecasts(F.build_features("QEUH", w2), model, h, test_rows=[i])["forecast"].iloc[0]
    assert base == pytest.approx(again)


def test_flag_rule_uses_only_pre_test_data():
    weekly = F.load_weekly()
    base = F.build_features("QEUH", weekly)["flagged"]
    w2 = weekly.copy()
    w2.loc[w2.week_ending >= F.TEST_START, "att_QEUH"] = 99999    # change only test-period attendance
    assert (F.build_features("QEUH", w2).loc[w2.week_ending < F.TEST_START, "flagged"].values
            == base[weekly.week_ending < F.TEST_START].values).all()


def test_flag_exclusion_matches_the_inputs_of_each_horizon():
    df = F.build_features("RHC")
    for h in (1, 2, 4):
        fl = F.flag_any_h(df, h)
        i = int(np.where(df["flagged"].values == 1)[0][0]) + h + 1        # lag_{h+1} points at a flagged week
        assert fl.iloc[i] == 1
        i2 = int(np.where(df["flagged"].values == 1)[0][0]) + h + 2
        assert fl.iloc[i2] == (1 if df["flagged"].iloc[i2 - 52] or df["flagged"].iloc[i2] else
                               int(df["flagged"].iloc[i2 - h] or df["flagged"].iloc[i2 - h - 1]))


def test_hac_dm_reduces_to_plain_dm_without_lags():
    rng = np.random.default_rng(3)
    e1, e2 = rng.normal(0, 8, 120), rng.normal(0, 10, 120)
    a = F.diebold_mariano(e1, e2, 1)
    b = F.diebold_mariano_hac(e1, e2, 1, lags=0)
    assert a[0] == pytest.approx(b[0]) and a[1] == pytest.approx(b[1])


def test_baselines_match_definitions():
    df = F.build_features("GRI")
    b = F.baseline_forecasts(df, 1)
    sub = df.iloc[F.test_indices(df, 1)]
    assert np.allclose(b[b.model == "B2"]["forecast"], sub["lag_1"])
    assert np.allclose(b[b.model == "B1"]["forecast"], sub["lag_52"])
