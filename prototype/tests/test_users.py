import json
import os
import stat
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import users as U  # noqa: E402


@pytest.fixture
def store(tmp_path):
    return U.UserStore(str(tmp_path / "users.json"))


def test_add_and_verify(store):
    assert not store.any_users()
    assert store.add("  A.   Officer ", "correct horse battery") == "A. Officer"
    assert store.verify("A. Officer", "correct horse battery") == "A. Officer"
    assert store.verify("a. officer", "correct horse battery") == "A. Officer"   # name match ignores case
    assert store.any_users() and store.names() == ["A. Officer"]


@pytest.mark.parametrize("name,pw", [("A. Officer", "wrong password!"), ("Nobody", "correct horse battery"),
                                     ("A. Officer", ""), ("", "correct horse battery"), (None, None)])
def test_wrong_credentials_are_refused(store, name, pw):
    store.add("A. Officer", "correct horse battery")
    assert store.verify(name, pw) is None


def test_password_is_not_stored_in_clear_and_file_is_private(store):
    store.add("A. Officer", "correct horse battery")
    raw = open(store.path).read()
    assert "correct horse battery" not in raw
    assert stat.S_IMODE(os.stat(store.path).st_mode) == 0o600
    assert len(json.loads(raw)["a. officer"]["hash"]) == 64


def test_same_password_gets_different_hashes(store):
    store.add("One Officer", "correct horse battery")
    store.add("Two Officer", "correct horse battery")
    d = json.load(open(store.path))
    assert d["one officer"]["hash"] != d["two officer"]["hash"]


def test_duplicate_short_password_and_bad_names_are_rejected(store):
    store.add("A. Officer", "correct horse battery")
    with pytest.raises(U.UserError):
        store.add("a. OFFICER", "another long password")
    with pytest.raises(U.UserError):
        store.add("B. Officer", "short")
    for bad in ("", " ", "x", "y" * 41, "bad\x00name"):
        with pytest.raises(U.UserError):
            store.add(bad, "correct horse battery")
    assert U.clean_name("bad\nname") == "bad name"      # line breaks cannot reach the log: they become a space


# ---- command line decisions respect the accounts
def test_cli_decisions_need_the_password_once_accounts_exist(tmp_path, monkeypatch, capsys):
    import getpass
    import alert_tool as T
    import alerts as A
    monkeypatch.setattr(T, "OUT", str(tmp_path))
    monkeypatch.setattr(T, "LOG", str(tmp_path / "log.jsonl"))
    monkeypatch.setattr(T, "USERS", str(tmp_path / "users.json"))
    log = A.AlertLog(T.LOG)
    a = log.create("QEUH", "2026-10-25", 2100, "high", "M2t")
    b = log.create("GRI", "2026-10-25", 1900, "high", "M2t")
    # no accounts yet: allowed, with a warning
    T.main(["approve", a.id, "--officer", "Anyone"])
    assert "NOT verified" in capsys.readouterr().out and log.get(a.id).decided_by == "Anyone"
    # accounts exist: wrong password refused, right password accepted under the stored name
    T.user_store().add("A. Officer", "correct horse battery")
    monkeypatch.setattr(getpass, "getpass", lambda *_: "wrong password!!")
    with pytest.raises(SystemExit):
        T.main(["approve", b.id, "--officer", "A. Officer"])
    assert log.get(b.id).status == "pending"
    monkeypatch.setattr(getpass, "getpass", lambda *_: "correct horse battery")
    T.main(["approve", b.id, "--officer", "a. officer"])
    assert log.get(b.id).decided_by == "A. Officer"


def test_password_length_is_bounded(store):
    with pytest.raises(U.UserError):
        store.add("A. Officer", "x" * (U.MAX_PASSWORD + 1))
    store.add("A. Officer", "x" * U.MAX_PASSWORD)
    assert store.verify("A. Officer", "x" * U.MAX_PASSWORD)


def test_adduser_needs_an_existing_officer_once_accounts_exist(tmp_path, monkeypatch):
    import getpass
    import alert_tool as T
    monkeypatch.setattr(T, "USERS", str(tmp_path / "users.json"))
    pws = iter(["first password!", "first password!"])
    monkeypatch.setattr(getpass, "getpass", lambda *_: next(pws))
    T.main(["adduser", "First Officer"])                          # no accounts yet: allowed
    pws = iter(["wrong password!!", "second password", "second password"])
    monkeypatch.setattr(getpass, "getpass", lambda *_: next(pws))
    monkeypatch.setattr("builtins.input", lambda *_: "First Officer")
    with pytest.raises(SystemExit):                               # authoriser's password is wrong
        T.main(["adduser", "Mallory"])
    assert T.user_store().names() == ["First Officer"]
    pws = iter(["first password!", "second password", "second password"])
    monkeypatch.setattr(getpass, "getpass", lambda *_: next(pws))
    T.main(["adduser", "Second Officer"])
    assert T.user_store().names() == ["First Officer", "Second Officer"]
