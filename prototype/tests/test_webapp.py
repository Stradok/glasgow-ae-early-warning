import http.client
import json
import os
import re
import sys
import threading
import urllib.parse

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import alert_tool as T  # noqa: E402
import alerts as A  # noqa: E402
import users as U  # noqa: E402
import webapp as W  # noqa: E402

PW = "correct horse battery"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "OUT", str(tmp_path / "out"))
    log = A.AlertLog(str(tmp_path / "out" / "log.jsonl"))
    store = U.UserStore(str(tmp_path / "out" / "users.json"))
    store.add("A. Officer", PW)
    store.add("B. Officer", PW)
    app = W.App(log, store, True, "2026-10-18", str(tmp_path / "out" / "released"), T)
    srv = W.make_server(app, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield app, srv.server_address[1], log
    srv.shutdown()
    srv.server_close()


class Client:
    def __init__(self, port):
        self.port, self.cookie = port, None

    def req(self, method, path, data=None, host=None, cookie=True):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if self.cookie and cookie:
            h["Cookie"] = self.cookie
        body = urllib.parse.urlencode(data) if data is not None else None
        if body:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        txt = r.read().decode()
        sc = r.getheader("Set-Cookie")
        if sc and "session=" in sc and not sc.startswith("session=;"):
            self.cookie = sc.split(";")[0]
        return r.status, txt, r

    def login(self, name="A. Officer", pw=PW):
        return self.req("POST", "/login", {"name": name, "password": pw})

    def csrf(self):
        s, t, _ = self.req("GET", "/")
        assert s == 200
        return re.search(r"name='csrf' value='([^']+)'", t).group(1)


def pending(log, **kw):
    return log.create("QEUH", "2026-10-25", 2100, "high", "M2t", [["time of year", 20.0]])


def test_requires_login(env):
    _, port, log = env
    a = pending(log)
    s, _, r = Client(port).req("GET", "/")
    assert s == 303 and r.getheader("Location") == "/login"
    s, _, _ = Client(port).req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": "x", "officer": "Mallory"})
    assert s == 303 and log.get(a.id).status == "pending"            # nothing was decided


def test_wrong_host_header_is_refused(env):
    _, port, _ = env
    s, _, _ = Client(port).req("GET", "/login", host="evil.example:80")
    assert s == 400


def test_login_sets_safe_cookie_and_wrong_password_fails(env):
    _, port, _ = env
    c = Client(port)
    s, _, _ = c.login(pw="wrong password!!")
    assert s == 401 and c.cookie is None
    s, _, r = c.login()
    assert s == 303
    sc = r.getheader("Set-Cookie")
    assert "HttpOnly" in sc and "SameSite=Strict" in sc
    assert "frame-ancestors 'none'" in r.getheader("Content-Security-Policy")


def test_lockout_after_repeated_failures_even_for_right_password(env):
    _, port, _ = env
    c = Client(port)
    for _ in range(W.MAX_FAILS):
        assert c.login(pw="wrong password!!")[0] == 401
    assert c.login()[0] == 429
    assert Client(port).login("B. Officer")[0] == 303            # other officers are not affected


def test_decision_needs_csrf_token(env):
    _, port, log = env
    a = pending(log)
    c = Client(port)
    c.login()
    for tok in ("", "forged"):
        s, _, _ = c.req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": tok})
        assert s == 403
    assert log.get(a.id).status == "pending"


def test_approval_is_logged_under_the_logged_in_name_not_the_form(env):
    _, port, log = env
    a = pending(log)
    c = Client(port)
    c.login("A. Officer")
    s, _, _ = c.req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": c.csrf(),
                                        "officer": "Dr Someone Else", "note": "checked"})
    assert s == 303
    got = log.get(a.id)
    assert got.status == "approved" and got.decided_by == "A. Officer"
    assert not any("Someone Else" in str(e) for e in log.events())


def test_rejection_needs_a_reason_and_release_needs_approval(env):
    _, port, log = env
    a = pending(log)
    c = Client(port)
    c.login()
    tok = c.csrf()
    c.req("POST", "/decide", {"id": a.id, "action": "reject", "csrf": tok, "note": "  "})
    c.req("POST", "/decide", {"id": a.id, "action": "release", "csrf": tok})
    assert log.get(a.id).status == "pending"
    _, page, _ = c.req("GET", "/")
    assert "Refused" in page
    c.req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": tok})
    c.req("POST", "/decide", {"id": a.id, "action": "release", "csrf": tok})
    assert log.get(a.id).status == "released"
    assert os.path.exists(os.path.join(app_released(env), f"alert_{a.id}.txt"))


def app_released(env):
    return env[0].released_dir


def test_a_decided_alert_cannot_be_decided_again(env):
    _, port, log = env
    a = pending(log)
    c1, c2 = Client(port), Client(port)
    c1.login("A. Officer"); c2.login("B. Officer")
    c1.req("POST", "/decide", {"id": a.id, "action": "reject", "csrf": c1.csrf(), "note": "known event"})
    c2.req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": c2.csrf()})
    got = log.get(a.id)
    assert got.status == "rejected" and got.decided_by == "A. Officer"


def test_user_text_is_escaped(env):
    _, port, log = env
    a = pending(log)
    c = Client(port)
    c.login()
    c.req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": c.csrf(),
                              "note": "<script>alert(1)</script>"})
    _, page, _ = c.req("GET", "/")
    assert "<script>alert(1)" not in page and "&lt;script&gt;alert(1)" in page


def test_tampered_log_is_reported_and_blocks_decisions(env):
    _, port, log = env
    a = pending(log)
    c = Client(port)
    c.login()
    tok = c.csrf()
    text = open(log.path).read()
    assert '"forecast": 2100.0' in text
    open(log.path, "w").write(text.replace('"forecast": 2100.0', '"forecast": 9999.0'))
    _, page, _ = c.req("GET", "/")
    assert "integrity check FAILED" in page
    c.req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": tok})
    _, page, _ = c.req("GET", "/")
    assert "Refused" in page and "integrity" in page                  # the decision itself was refused, not just the display
    assert [json.loads(x)["event"] for x in open(log.path)] == ["created"]       # no approval event was appended


def test_logout_ends_the_session(env):
    _, port, _ = env
    c = Client(port)
    c.login()
    assert c.req("GET", "/")[0] == 200
    c.req("POST", "/logout", {"csrf": c.csrf()})
    assert c.req("GET", "/")[0] == 303


def test_demo_forecast_runs_from_the_page(env):
    _, port, log = env
    c = Client(port)
    c.login()
    s, _, _ = c.req("POST", "/run", {"csrf": c.csrf()})
    assert s == 303
    _, page, _ = c.req("GET", "/")
    assert "Forecast: week ending 2026-10-18" in page and "Queen Elizabeth University Hospital" in page
    assert os.path.exists(T.latest_path(True))


def test_release_is_logged_under_the_person_who_pressed_it(env):
    _, port, log = env
    a = pending(log)
    c1, c2 = Client(port), Client(port)
    c1.login("A. Officer"); c2.login("B. Officer")
    c1.req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": c1.csrf()})
    c2.req("POST", "/decide", {"id": a.id, "action": "release", "csrf": c2.csrf()})
    rel = [e for e in log.events() if e["event"] == "released"][0]
    assert rel["officer"] == "A. Officer" and rel["released_by"] == "B. Officer"
    assert "Released by: B. Officer" in open(os.path.join(env[0].released_dir, f"alert_{a.id}.txt")).read()


def test_lockout_cannot_be_dodged_with_spacing_or_case(env):
    _, port, _ = env
    c = Client(port)
    variants = ["A. Officer", "A.  Officer", "a. officer", "A.   OFFICER", " A. Officer"]
    for v in variants:
        assert c.login(v, "wrong password!!")[0] == 401
    for v in variants + ["A.    Officer"]:
        assert c.login(v, PW)[0] == 429                               # the right password is refused too while locked


def test_parallel_guesses_are_limited(env):
    _, port, _ = env
    codes = []

    def guess():
        codes.append(Client(port).login("B. Officer", "wrong password!!")[0])

    ts = [threading.Thread(target=guess) for _ in range(30)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert codes.count(401) <= W.MAX_FAILS and codes.count(429) >= 30 - W.MAX_FAILS


def test_locked_name_stays_locked_during_a_flood_of_random_names(env):
    app, port, _ = env
    for _ in range(W.MAX_FAILS):
        app.begin_attempt("A. Officer")
    for i in range(1500):
        app.begin_attempt(f"random-{i}")
    assert not app.begin_attempt("A. Officer")                       # eviction never frees a locked name
    assert len(app.fails) <= 1001


def test_negative_or_bad_content_length_does_not_hang(env):
    _, port, _ = env
    for cl in ("-1", "abc", str(W.MAX_BODY + 1)):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        c.putrequest("POST", "/login", skip_host=True)
        c.putheader("Host", f"127.0.0.1:{port}"); c.putheader("Content-Length", cl)
        c.endheaders()
        assert c.getresponse().status == 413


def test_non_ascii_csrf_is_a_403_not_a_crash(env):
    _, port, log = env
    a = pending(log)
    c = Client(port)
    c.login()
    s, _, _ = c.req("POST", "/decide", {"id": a.id, "action": "approve", "csrf": "é"})
    assert s == 403 and log.get(a.id).status == "pending"
    assert c.req("GET", "/")[0] == 200                               # the server is still fine


def test_corrupt_or_empty_saved_forecast_means_no_forecast_not_a_500(env):
    _, port, _ = env
    c = Client(port)
    c.login()
    os.makedirs(os.path.dirname(T.latest_path(True)), exist_ok=True)
    for bad in ("{not json", '{"results": []}', '{"results": [{"x": 1}]}', "[]"):
        open(T.latest_path(True), "w").write(bad)
        s, page, _ = c.req("GET", "/")
        assert s == 200 and "No forecast yet" in page


def test_demo_mode_never_touches_the_real_log_forecast_or_report(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(T, "OUT", str(out))
    monkeypatch.setattr(T, "LOG", str(out / "alert_log.jsonl"))
    monkeypatch.setattr(T, "LOG_DEMO", str(out / "alert_log_demo.jsonl"))
    monkeypatch.setattr(T, "USERS", str(tmp_path / "users.json"))
    T.user_store().add("A. Officer", PW)
    app = W.build_app(T, True, "2026-10-18")
    srv = W.make_server(app, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = Client(srv.server_address[1])
        c.login()
        c.req("POST", "/run", {"csrf": c.csrf()})
    finally:
        srv.shutdown(); srv.server_close()
    names = set(os.listdir(out))
    assert "latest_forecast_demo.json" in names and "forecast_demo_2026-10-18.html" in names
    assert not {"alert_log.jsonl", "latest_forecast.json", "forecast_2026-10-18.html"} & names


def test_real_mode_run_uses_real_files_and_the_refresh_option(tmp_path, monkeypatch):
    import pandas as pd
    out = tmp_path / "out"
    monkeypatch.setattr(T, "OUT", str(out))
    monkeypatch.setattr(T, "LOG", str(out / "alert_log.jsonl"))
    monkeypatch.setattr(T, "LOG_DEMO", str(out / "alert_log_demo.jsonl"))
    monkeypatch.setattr(T, "USERS", str(tmp_path / "users.json"))
    T.user_store().add("A. Officer", PW)
    refreshed = []
    monkeypatch.setattr(T.D, "refresh_history", lambda *a, **k: refreshed.append(1))      # no network
    target = T.D.load_history()["week_ending"].max() + pd.Timedelta(days=7)
    days = pd.DataFrame({"date": pd.date_range(end=target, periods=7), "tmean": 9.0, "tmax": 12.0, "tmin": 6.0})
    monkeypatch.setattr(T.D, "fetch_forecast_days", lambda we: days)
    app = W.build_app(T, False, None)
    srv = W.make_server(app, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = Client(srv.server_address[1])
        c.login()
        c.req("POST", "/run", {"csrf": c.csrf(), "refresh": "1"})
    finally:
        srv.shutdown(); srv.server_close()
    assert refreshed == [1]
    names = set(os.listdir(out))
    assert "latest_forecast.json" in names and f"forecast_{target.date()}.html" in names
    assert "latest_forecast_demo.json" not in names and "alert_log_demo.jsonl" not in names


def test_script_nonce_matches_header_is_fresh_and_absent_where_unneeded(env):
    _, port, _ = env
    c = Client(port)
    s, _, r = c.req("GET", "/login")
    assert "script-src 'none'" in r.getheader("Content-Security-Policy") and "nonce" not in r.getheader("Content-Security-Policy")
    c.login()
    seen = []
    for _ in range(2):
        s, page, r = c.req("GET", "/")
        header_nonce = re.search(r"script-src 'nonce-([^']+)'", r.getheader("Content-Security-Policy")).group(1)
        assert f'<script nonce="{header_nonce}">' in page and len(header_nonce) >= 20
        seen.append(header_nonce)
    assert seen[0] != seen[1]                                      # fresh per response
    s, _, r = c.req("GET", "/nope")
    assert s == 404 and "script-src 'none'" in r.getheader("Content-Security-Policy")
    s, _, r = c.req("GET", "/", host="evil.example")
    assert s == 400 and "script-src 'none'" in r.getheader("Content-Security-Policy")


def test_a_bad_saved_forecast_leaves_the_page_usable_with_sign_out(env):
    _, port, _ = env
    c = Client(port)
    c.login()
    os.makedirs(os.path.dirname(T.latest_path(True)), exist_ok=True)
    open(T.latest_path(True), "w").write(json.dumps({"saved_at": "x", "results": [
        {"site": "QEUH", "target_week": "2026-10-25", "forecast": 1.0, "risk": "high", "last_week": 1.0,
         "p75": 0.0, "p90": 0.0, "drivers": [], "history": []}]}))
    s, page, _ = c.req("GET", "/")
    assert s == 200 and "No forecast yet" in page and "Sign out" in page and "Run the demo forecast" in page
