import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alert_tool as T  # noqa: E402
import alerts as A  # noqa: E402
import data_access as D  # noqa: E402
import users as U  # noqa: E402


@pytest.fixture
def empty(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(T, "OUT", str(out))
    monkeypatch.setattr(T, "LOG", str(out / "alert_log.jsonl"))
    monkeypatch.setattr(T, "LOG_DEMO", str(out / "alert_log_demo.jsonl"))
    monkeypatch.setattr(T, "USERS", str(tmp_path / "accounts" / "users.json"))
    monkeypatch.setattr(D, "DATA", str(tmp_path / "data"))
    return tmp_path


def done(steps):
    return [ok for ok, _, _ in steps]


def test_fresh_checkout_points_to_creating_an_account_and_creates_nothing(empty, capsys):
    steps = T.guide_steps(demo=True)
    assert [what for ok, what, _ in steps if not ok][0].startswith("At least one officer account")
    T.main(["--demo", "guide"])
    out = capsys.readouterr().out
    assert "Next step: At least one officer account exists" in out and 'adduser "Your Name"' in out
    assert list(empty.iterdir()) == []                              # read-only: no folders, files or locks appear


def test_real_mode_asks_for_live_data_and_demo_mode_does_not(empty):
    U.UserStore(T.USERS).add("A. Officer", "correct horse battery")
    real = [(ok, what) for ok, what, _ in T.guide_steps(demo=False)]
    assert (False, "Live data pulled (prototype/data/)") in real
    assert all("Live data" not in what for _, what, _ in T.guide_steps(demo=True))


def test_pending_alert_and_unreadable_log_are_reported(empty, capsys):
    U.UserStore(T.USERS).add("A. Officer", "correct horse battery")
    log = A.AlertLog(T.LOG_DEMO)
    log.create("QEUH", "2026-10-25", 1960.0, "high", "M2t", [("time of year", 1.0)])
    assert done(T.guide_steps(demo=True))[-1] is False               # one alert is waiting
    with open(T.LOG_DEMO, "a") as f:
        f.write("not json\n")                                        # damaged log must be reported, not crash
    last = T.guide_steps(demo=True)[-1]
    assert last[0] is False and "unreadable" in last[1]
    T.main(["--demo", "guide"])
    assert "unreadable" in capsys.readouterr().out


def test_busy_port_gives_a_clear_message_not_a_traceback(empty):
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    port = s.getsockname()[1]
    try:
        with pytest.raises(SystemExit) as e:
            T.main(["--demo", "serve", "--port", str(port)])
    finally:
        s.close()
    msg = str(e.value)
    assert f"port {port}" in msg and f"--demo serve --port {port + 1}" in msg and "Traceback" not in msg   # demo stays demo


def test_a_non_port_oserror_is_not_blamed_on_the_port(empty, monkeypatch):
    import webapp
    def disk(*_a, **_k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(webapp, "serve", disk)
    with pytest.raises(OSError):
        T.main(["serve"])
