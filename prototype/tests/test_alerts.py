import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alerts as A  # noqa: E402


@pytest.fixture
def log(tmp_path):
    return A.AlertLog(str(tmp_path / "log.jsonl"))


def make(log, site="QEUH", week="2026-10-25", risk="high"):
    return log.create(site, week, 2100.4, risk, "M2t", [["time of year", 20.0]])


def test_new_alert_is_pending_and_logged(log):
    a = make(log)
    assert a.status == "pending"
    assert [e["event"] for e in log.events()] == ["created"]


@pytest.mark.parametrize("risk", ["low", "medium"])
def test_only_high_risk_becomes_an_alert(log, risk):
    with pytest.raises(A.AlertError):
        log.create("QEUH", "2026-10-25", 1500, risk, "M2t")


def test_rerun_does_not_duplicate_open_alert(log):
    a = make(log)
    b = make(log)
    assert a.id == b.id and len(log.alerts()) == 1


def test_approval_needs_named_officer(log):
    a = make(log)
    for bad in ("", "   ", None):
        with pytest.raises(A.AlertError):
            log.approve(a.id, bad)
    assert log.get(a.id).status == "pending"


def test_rejection_needs_reason(log):
    a = make(log)
    with pytest.raises(A.AlertError):
        log.reject(a.id, "Dr X", "  ")
    assert log.get(a.id).status == "pending"
    log.reject(a.id, "Dr X", "weather forecast unreliable")
    assert log.get(a.id).status == "rejected"


def test_cannot_release_unapproved_or_rejected(log, tmp_path):
    a = make(log)
    with pytest.raises(A.AlertError):
        log.release(a.id, str(tmp_path / "out"), "R. Officer")
    log.reject(a.id, "Dr X", "no")
    with pytest.raises(A.AlertError):
        log.release(a.id, str(tmp_path / "out"), "R. Officer")
    assert not os.path.exists(tmp_path / "out")


def test_approve_then_release_writes_message_and_audit_trail(log, tmp_path):
    a = make(log)
    log.approve(a.id, "Dr X", "ok")
    path = log.release(a.id, str(tmp_path / "out"), "R. Officer")
    text = open(path).read()
    assert "HIGH" in text and "Approved by: Dr X" in text and "Released by: R. Officer" in text and "not a diagnosis" in text
    events = log.events()
    assert [e["event"] for e in events] == ["created", "approved", "released"]
    assert events[1]["officer"] == "Dr X"
    assert events[2]["released_by"] == "R. Officer" and events[2]["officer"] == "Dr X"   # releaser is recorded, not just the approver
    assert log.get(a.id).status == "released"


def test_release_needs_a_named_officer(log, tmp_path):
    a = make(log)
    log.approve(a.id, "Dr X", "ok")
    for bad in ("", "  ", None):
        with pytest.raises(A.AlertError):
            log.release(a.id, str(tmp_path / "out"), bad)
    assert log.get(a.id).status == "approved"


def test_cannot_decide_twice(log):
    a = make(log)
    log.approve(a.id, "Dr X")
    with pytest.raises(A.AlertError):
        log.reject(a.id, "Dr Y", "changed my mind")
    with pytest.raises(A.AlertError):
        log.approve(a.id, "Dr Y")


def _tamper(path, fn):
    lines = open(path).read().splitlines()
    fn(lines)
    open(path, "w").write("\n".join(lines) + "\n")


def test_editing_the_log_is_detected(log):
    a = make(log)
    log.approve(a.id, "Dr X")
    _tamper(log.path, lambda ls: ls.__setitem__(1, ls[1].replace("Dr X", "Dr Y")))
    with pytest.raises(A.AlertError, match="integrity"):
        log.get(a.id)


def test_deleting_or_reordering_events_is_detected(log):
    a = make(log)
    log.approve(a.id, "Dr X")
    path = log.path
    original = open(path).read().splitlines()
    open(path, "w").write(original[1] + "\n")                  # drop the creation event
    with pytest.raises(A.AlertError):
        log.alerts()
    open(path, "w").write("\n".join(reversed(original)) + "\n")
    with pytest.raises(A.AlertError):
        log.alerts()


def test_forged_approval_line_is_rejected(log, tmp_path):
    a = make(log)
    with open(log.path, "a") as f:                           # raw append without the hash chain
        f.write(json.dumps({"event": "approved", "alert_id": a.id, "officer": ""}) + "\n")
    with pytest.raises(A.AlertError):
        log.release(a.id, str(tmp_path / "out"), "R. Officer")
    assert not os.path.exists(tmp_path / "out")


def test_forged_event_with_valid_hash_but_no_officer_is_rejected(log):
    """Even a correctly chained event is refused on replay if it breaks the rules."""
    a = make(log)
    with log._lock():
        log._append({"event": "approved", "alert_id": a.id, "officer": "", "note": None})
    with pytest.raises(A.AlertError, match="officer"):
        log.alerts()


def test_double_decision_in_log_is_inconsistent(log):
    a = make(log)
    log.approve(a.id, "Dr X")
    with log._lock():                                         # simulates a race that slipped past the checks
        log._append({"event": "rejected", "alert_id": a.id, "officer": "Dr Y", "note": "late"})
    with pytest.raises(A.AlertError, match="decided"):
        log.alerts()


def test_stale_second_decision_is_refused_under_the_lock(log):
    a = make(log)
    stale = A.AlertLog(log.path)                              # a second officer's session
    log.approve(a.id, "Dr X")
    with pytest.raises(A.AlertError):
        stale.reject(a.id, "Dr Y", "too late")
    assert log.get(a.id).status == "approved"


def test_empty_or_short_id_is_refused(log):
    a = make(log)
    for bad in ("", "  ", a.id[:2], None):
        with pytest.raises(A.AlertError):
            log.approve(bad, "Dr X")
    assert log.get(a.id).status == "pending"


def test_rejection_is_final_for_that_site_and_week(log):
    a = make(log)
    log.reject(a.id, "Dr X", "known event")
    again = make(log)                                         # a re-run of the forecast
    assert again.id == a.id and again.status == "rejected"
    assert len(log.alerts()) == 1


def test_duplicate_created_event_is_refused(log):
    a = make(log)
    with log._lock():
        log._append({"event": "created", "alert": {"id": a.id, "site": "GRI", "target_week": "2026-11-01",
                                                    "forecast": 1.0, "risk": "high", "model": "M2t", "drivers": []}})
    with pytest.raises(A.AlertError, match="twice"):
        log.alerts()


def test_failed_release_logging_publishes_nothing(log, tmp_path, monkeypatch):
    a = make(log)
    log.approve(a.id, "Dr X")
    monkeypatch.setattr(log, "_append", lambda e: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        log.release(a.id, str(tmp_path / "out"), "R. Officer")
    assert not any(n.endswith(".txt") for n in os.listdir(tmp_path / "out"))


def test_log_is_append_only_and_valid_json(log):
    a = make(log)
    before = open(log.path).read()
    log.approve(a.id, "Dr X")
    after = open(log.path).read()
    assert after.startswith(before)                       # earlier lines untouched
    for line in after.splitlines():
        json.loads(line)


def test_short_id_prefix_and_unknown_id(log):
    a = make(log)
    assert log.get(a.id[:4]).id == a.id
    with pytest.raises(A.AlertError):
        log.get("zzzz")
