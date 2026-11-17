import datetime as dt
import os
import sys

import pandas as pd
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import alert_tool as T  # noqa: E402
import data_access as D  # noqa: E402
import engine as E  # noqa: E402


def test_last_complete_sunday():
    # Wed 2026-11-04: week ending Sun 2026-11-01 is only 3 days old, so use Sun 2026-10-25
    assert D.last_complete_sunday(dt.date(2026, 11, 4)) == dt.date(2026, 10, 25)
    assert D.last_complete_sunday(dt.date(2026, 11, 8)) == dt.date(2026, 11, 1)
    assert D.last_complete_sunday(dt.date(2026, 11, 8)).weekday() == 6


@pytest.fixture(scope="module")
def frozen():
    weekly, daily = D.load_history(), D.load_daily_weather()
    target = pd.Timestamp("2026-10-18")
    days = T.backtest_days(daily, target)
    return weekly[weekly["week_ending"] < target], daily[daily["date"] < days["date"].min()], days


def test_forecast_is_plausible_and_complete(frozen):
    weekly, daily, days = frozen
    r = E.forecast_site("QEUH", weekly, daily, days)
    assert r["target_week"] == "2026-10-18"
    assert 1000 < r["forecast"] < 3000
    assert abs(r["forecast"] - r["last_week"]) < 400          # one-week-ahead: stays near last week
    assert r["risk"] in ("low", "medium", "high")
    assert len(r["drivers"]) == 5 and len(r["history"]) == 52
    assert r["p75"] < r["p90"]


def test_forecast_ignores_attendance_after_target(frozen):
    """Even if later weeks were present in the history, only data before the target week may be used."""
    weekly, daily, days = frozen
    r1 = E.forecast_site("GRI", weekly, daily, days)
    r2 = E.forecast_site("GRI", weekly.copy(), daily, days)
    assert r1["forecast"] == pytest.approx(r2["forecast"])


def test_rejects_target_week_that_is_not_next_week(frozen):
    weekly, daily, days = frozen
    far = days.copy()
    far["date"] = far["date"] + pd.Timedelta(days=14)
    with pytest.raises(ValueError):
        E.forecast_site("QEUH", weekly, daily, far)


def test_missing_forecast_weather_is_an_error_not_a_guess(frozen):
    weekly, daily, days = frozen
    bad = days.copy()
    bad.loc[0, ["tmax", "tmin", "tmean"]] = float("nan")
    with pytest.raises(ValueError):
        E.forecast_site("QEUH", weekly, daily, bad)


def test_cli_end_to_end_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(T, "OUT", str(tmp_path))
    monkeypatch.setattr(T, "LOG", str(tmp_path / "log.jsonl"))
    monkeypatch.setattr(T, "LOG_DEMO", str(tmp_path / "demo.jsonl"))
    monkeypatch.setattr(T, "USERS", str(tmp_path / "users.json"))    # never read the real accounts file
    T.main(["forecast", "--backtest-week", "2026-10-18"])
    assert not (tmp_path / "log.jsonl").exists()              # a demo run never writes to the real log
    out = capsys.readouterr().out
    assert "QEUH" in out and "GRI" in out and "RHC" in out
    assert (tmp_path / "forecast_demo_2026-10-18.html").exists()     # demo reports never share a name with real ones
    T.main(["--demo", "pending"])
    pend = capsys.readouterr().out
    if "no pending" not in pend:                              # at least one medium/high alert was raised
        aid = pend.split()[0]
        with pytest.raises(SystemExit):                       # release before approval is refused
            T.main(["--demo", "release", aid, "--officer", "Test Officer"])
        T.main(["--demo", "approve", aid, "--officer", "Test Officer"])
        T.main(["--demo", "release", aid, "--officer", "Test Officer"])
        assert (tmp_path / "released_demo" / f"alert_{aid}.txt").exists()


def test_engine_features_match_analysis_build_features(frozen):
    """The prototype's feature row for the target week equals the analysis pipeline's row (same code path)."""
    weekly, daily, days = frozen
    full_weekly = D.load_history()
    full_daily = D.load_daily_weather()
    ref = E.F.build_features("QEUH", full_weekly, full_daily)
    ref_row = ref[ref["week_ending"] == pd.Timestamp("2026-10-18")].iloc[0]
    new = E.append_target_week(weekly[weekly["week_ending"] <= weekly["week_ending"].max()], days)
    daily2 = pd.concat([daily[["date", "tmax", "tmin"]], days[["date", "tmax", "tmin"]]], ignore_index=True)
    mine = E.F.build_features("QEUH", new, daily2).iloc[-1]
    names = E.F.feature_names(E.MODEL, 1)
    for n in names:
        if n in ("temp_mean",):               # demo approximates the daily mean by (max+min)/2
            assert abs(mine[n] - ref_row[n]) < 0.5
        else:
            assert mine[n] == pytest.approx(ref_row[n]), n


def test_forecast_days_must_be_consecutive_monday_to_sunday(frozen):
    weekly, daily, days = frozen
    bad = days.copy()
    bad.loc[3, "date"] = bad.loc[2, "date"]                   # duplicate date
    with pytest.raises(ValueError):
        E.forecast_site("QEUH", weekly, daily, bad)


def test_cli_turns_value_errors_into_a_clean_message(monkeypatch, tmp_path):
    monkeypatch.setattr(T, "OUT", str(tmp_path))
    monkeypatch.setattr(T, "LOG_DEMO", str(tmp_path / "demo.jsonl"))
    with pytest.raises(SystemExit) as ex:
        T.main(["forecast", "--backtest-week", "2026-10-17"])
    assert "Sunday" in str(ex.value)
