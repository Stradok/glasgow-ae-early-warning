import json
import os
import re
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alerts as A  # noqa: E402
import ui  # noqa: E402


def result(site="QEUH", risk="high", forecast=1960.0):
    return {"site": site, "target_week": "2026-10-25", "forecast": forecast, "risk": risk, "last_week": 1900.0,
            "p75": 1900.0, "p90": 1940.0, "model": "M2t",
            "drivers": [("time of year", 20.0), ("mean temperature this week", -35.0), ("bank holidays this week", 0.0)],
            "history": [1800.0 + 3 * i for i in range(52)]}


def alert(**kw):
    base = dict(id="abcd1234", site="QEUH", target_week="2026-10-25", forecast=1960.0, risk="high", model="M2t",
                drivers=[["time of year", 20.0]])
    base.update(kw)
    return A.Alert(**base)


def render(latest=True, user="A. Officer", alerts=None, flashes=(), intact=True, nonce="NONCE123"):
    lat = {"saved_at": "2026-11-14T10:00:00+00:00",
           "results": [result("QEUH"), result("GRI", "medium", 1920.0), result("RHC", "low", 1500.0)]} if latest else None
    return ui.dashboard(nonce=nonce, user=user, csrf="tok", flashes=list(flashes), demo=False, latest=lat,
                        alerts=alerts if alerts is not None else {"abcd1234": alert()}, events=[], intact=intact, error="")


@pytest.mark.parametrize("with_forecast", [True, False])
def test_every_tour_step_has_something_to_point_at(with_forecast):
    page = render(latest=with_forecast)
    present = set(re.findall(r"data-tour='([a-z]+)'", page))
    for step in ui.TOUR_STEPS:
        assert step["title"] and step["body"]
        assert not step["target"] or present & set(step["target"]), (step["title"], present)


def test_tour_button_and_script_are_wired_with_the_nonce():
    page = render(nonce="N0NC3")
    assert "id='tour-start'" in page and "Take the tour" in page
    scripts = re.findall(r"<script([^>]*)>", page)
    assert scripts == [' nonce="N0NC3"']                          # exactly one script, and it carries the nonce
    assert not re.search(r"\son[a-z]+\s*=", page)                  # no inline event handlers
    assert "http://" not in re.sub(r"xmlns='http://www.w3.org/2000/svg'", "", page).replace("%3Csvg xmlns='http://www.w3.org/2000/svg'", "")


def test_tour_autostarts_only_when_there_is_no_message_to_read():
    assert "<body data-autotour='1'>" in render()
    assert "<body>" in render(flashes=[("ok", "Forecast computed")])


def test_login_page_runs_no_script():
    page = ui.login_page("N", False, True)
    assert "<script" not in page


def test_hostile_text_cannot_reach_the_script_or_the_markup():
    evil = "</script><img src=x onerror=alert(1)>"
    clean = render(user="A. Officer")
    page = render(user=evil, alerts={"a": alert(id="</script>x", decided_by=evil, status="approved")},
                  flashes=[("err", evil)])
    assert "<img src=x onerror" not in page and "</script><img" not in page
    assert "&lt;/script&gt;&lt;img" in page
    script = lambda p: re.search(r"<script[^>]*>(.*?)</script>", p, re.S).group(1)
    assert script(page) == script(clean)                           # nothing from data is inside the script


def test_tour_steps_are_valid_json_in_the_script_and_no_closing_tags_leak():
    js = ui.tour_script("n")
    assert js.count("</script>") == 1                              # only the real closing tag
    m = re.search(r"var STEPS = (\[.*?\]);\n", js, re.S)
    assert json.loads(m.group(1).replace("<\\/", "</")) == ui.TOUR_STEPS


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_tour_javascript_has_valid_syntax(tmp_path):
    body = re.search(r"<script[^>]*>(.*?)</script>", ui.tour_script("n"), re.S).group(1)
    f = tmp_path / "tour.js"
    f.write_text(body)
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_risk_is_never_conveyed_by_colour_alone():
    page = render()
    for word in ("High", "Medium", "Low"):
        assert f">{word}</span>" in page


def test_chart_and_drivers_survive_edge_cases():
    flat = ui.chart_svg([1000.0] * 52, 1000.0, 1000.0, 1000.0)     # constant history: no division by zero
    assert "<svg" in flat and "nan" not in flat.lower()
    above = ui.chart_svg([1000.0] * 52, 5000.0, 1100.0, 1200.0)
    assert "nan" not in above.lower()
    assert ui.drivers_html([]) == ""
    assert "0" in ui.drivers_html([("x", 0.0)])                     # all-zero drivers: no division by zero


def test_forecast_page_content_and_empty_states():
    page = render()
    assert "Queen Elizabeth University Hospital" in page and "Needs your decision (1)" in page
    assert "Release message" not in page                            # only shown for an approved alert
    assert "No forecast yet" in render(latest=False)
    assert "No alerts are waiting" in render(alerts={})
    assert "Release message" in render(alerts={"a": alert(status="approved", decided_by="B. Officer")})


def test_summary_strip_counts_risks_and_waiting_alerts():
    page = render()                                   # one high, one medium, one low hospital; one pending alert
    assert "<div class='tile t-high'><b>1</b>" in page and "<div class='tile t-medium'><b>1</b>" in page
    assert "<div class='tile t-low'><b>1</b>" in page
    assert "<b>1</b><span>alert waiting</span>" in page and "href='#alerts'" in page and "id='alerts'" in page
    assert "<b>0</b><span>alerts waiting</span>" in render(alerts={})


def test_timestamp_is_readable_and_bad_input_does_not_crash():
    assert ui.nice_time("2026-11-15T03:14:20+00:00") == "15 Nov 2026, 03:14 UTC"
    assert ui.nice_time("garbage") == "garbage" and ui.nice_time(None) == "None"
    assert "Computed 14 Nov 2026, 10:00 UTC." in render()


# ---- review findings: one bad saved record must never take the whole page down
def test_all_zero_and_empty_history_do_not_crash_the_chart():
    assert "ZeroDivision" not in repr(ui.chart_svg([0.0] * 52, 0.0, 0.0, 0.0))     # all-zero data
    assert "<svg" in ui.chart_svg([0.0] * 52, 0.0, 0.0, 0.0)
    assert ui.chart_svg([], 10.0, 5.0, 8.0) == "" and ui.chart_svg([5.0], 10.0, 5.0, 8.0) == ""


@pytest.mark.parametrize("break_it", [
    lambda r: r.update(history=[]),
    lambda r: r.update(history=[1.0]),
    lambda r: r.pop("history"),
    lambda r: r.pop("last_week"),
    lambda r: r.update(risk="critical"),
    lambda r: r.update(site="XYZ"),
    lambda r: r.update(forecast=float("nan")),
    lambda r: r.update(history=[1.0] * 51 + [float("inf")]),
    lambda r: r.update(drivers=[["x", float("nan")]]),
    lambda r: r.update(drivers=["not a pair"]),
    lambda r: r.update(forecast="1900"),
])
def test_load_latest_rejects_any_unusable_record(tmp_path, monkeypatch, break_it):
    import alert_tool as T
    monkeypatch.setattr(T, "OUT", str(tmp_path))
    good, bad = result("QEUH"), result("GRI")
    break_it(bad)
    for results in ([bad], [good, bad]):                           # a bad record anywhere invalidates the file
        (tmp_path / "latest_forecast_demo.json").write_text(json.dumps({"saved_at": "x", "results": results}))
        assert T.load_latest(True) is None
    (tmp_path / "latest_forecast_demo.json").write_text(json.dumps({"saved_at": "x", "results": [good]}))
    assert T.load_latest(True) is not None                         # and a good file still loads


def test_data_sources_are_credited_and_not_endorsed_on_every_page():
    for page in (render(), render(latest=False), ui.login_page("N", False, True)):
        assert "Public Health Scotland" in page and "Open Government Licence v3.0" in page
        assert "Weather data by Open-Meteo.com" in page and "https://open-meteo.com/" in page
        assert "not endorsed by Public Health Scotland or the NHS" in page
