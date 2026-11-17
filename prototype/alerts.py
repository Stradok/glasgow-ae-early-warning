"""Alert records, officer approval and the audit log (requirement R4).

Design: an append-only JSON-lines event log is the single source of truth. An alert's current state is
derived by replaying its events, so nothing is ever overwritten and every decision stays auditable.

Rules enforced in code (not just in the UI) and re-checked every time the log is read:
  * an alert is created as "pending"; only a high-risk forecast becomes an alert;
  * approve/reject need a named officer (this module only requires a non-empty name; the web page and the command line
    verify the name against officer accounts in users.py before calling it); rejecting also needs a reason;
  * an alert can be decided once; only an approved alert can be released; a rejection is final for that site and week;
  * every event carries the hash of the previous one (a hash chain), so editing, reordering, inserting or removing a line
    in the middle is detected and the tool refuses to continue. The chain is not keyed and its head is not stored elsewhere,
    so removing the LAST lines, or rewriting the whole file with valid hashes, is NOT detected: it is tamper-evident
    against casual edits, not a defence against someone with write access to the file;
  * decisions run under a file lock and re-read the log inside the lock, so two officers cannot both decide;
  * releasing logs the event first and only then publishes the message file.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field

GENESIS = "0" * 64
MIN_ID = 4


class AlertError(Exception):
    """Raised when an action breaks an approval rule or the log fails its integrity check."""


@dataclass
class Alert:
    id: str
    site: str
    target_week: str            # week-ending date (Sunday), ISO format
    forecast: float
    risk: str                   # "high"
    model: str
    drivers: list = field(default_factory=list)   # [[feature, contribution], ...]
    status: str = "pending"     # pending | approved | rejected | released
    decided_by: str | None = None
    decision_note: str | None = None
    created_at: str = ""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _digest(event: dict, prev: str) -> str:
    body = json.dumps({k: v for k, v in event.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


class AlertLog:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    # ---- low level
    @contextlib.contextmanager
    def _lock(self):
        with open(self.path + ".lock", "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

    def events(self) -> list[dict]:
        """All events, after verifying the hash chain."""
        if not os.path.exists(self.path):
            return []
        out, prev = [], GENESIS
        with open(self.path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    raise AlertError(f"audit log is corrupt at line {n} (not valid JSON)")
                if e.get("prev") != prev or e.get("hash") != _digest(e, prev):
                    raise AlertError(f"audit log failed its integrity check at line {n}: the log was edited or is not from this tool")
                prev = e["hash"]
                out.append(e)
        return out

    def _append(self, event: dict) -> None:
        """Append one event. Call only while holding the lock."""
        evs = self.events()
        prev = evs[-1]["hash"] if evs else GENESIS
        event = {"ts": _now(), **event, "prev": prev}
        event["hash"] = _digest(event, prev)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    # ---- state (replay with validation)
    def alerts(self) -> dict[str, Alert]:
        out: dict[str, Alert] = {}
        for e in self.events():
            kind = e["event"]
            if kind == "created":
                a = e["alert"]
                if a["id"] in out:
                    raise AlertError(f"log inconsistent: alert {a['id']} created twice")
                out[a["id"]] = Alert(**{**a, "status": "pending", "created_at": e["ts"]})
                continue
            al = out.get(e.get("alert_id"))
            if al is None:
                raise AlertError(f"log inconsistent: '{kind}' refers to an unknown alert")
            if kind in ("approved", "rejected"):
                if al.status != "pending":
                    raise AlertError(f"log inconsistent: alert {al.id} decided while '{al.status}'")
                if not (e.get("officer") or "").strip():
                    raise AlertError(f"log inconsistent: '{kind}' without a named officer on alert {al.id}")
                if kind == "rejected" and not (e.get("note") or "").strip():
                    raise AlertError(f"log inconsistent: rejection without a reason on alert {al.id}")
                al.status, al.decided_by, al.decision_note = kind, e["officer"], e.get("note")
            elif kind == "released":
                if al.status != "approved":
                    raise AlertError(f"log inconsistent: alert {al.id} released while '{al.status}'")
                al.status = "released"
            else:
                raise AlertError(f"log inconsistent: unknown event '{kind}'")
        return out

    def get(self, alert_id: str) -> Alert:
        alert_id = (alert_id or "").strip()
        if len(alert_id) < MIN_ID:
            raise AlertError(f"give at least {MIN_ID} characters of the alert id")
        al = self.alerts()
        matches = [k for k in al if k == alert_id or k.startswith(alert_id)]
        if len(matches) != 1:
            raise AlertError(f"alert '{alert_id}' not found" if not matches else f"'{alert_id}' is ambiguous")
        return al[matches[0]]

    # ---- actions
    def create(self, site: str, target_week: str, forecast: float, risk: str, model: str,
               drivers: list | None = None) -> Alert:
        if risk != "high":
            raise AlertError("only a high-risk forecast becomes an alert (the medium tier was not evaluated)")
        with self._lock():
            # one alert per site and week: re-runs never duplicate it, and a rejection stays rejected
            for a in self.alerts().values():
                if a.site == site and a.target_week == target_week:
                    return a
            a = Alert(id=uuid.uuid4().hex[:8], site=site, target_week=target_week, forecast=round(float(forecast), 1),
                      risk=risk, model=model, drivers=[[n, round(float(c), 2)] for n, c in (drivers or [])])
            self._append({"event": "created", "alert": {k: v for k, v in a.__dict__.items()
                                                        if k not in ("status", "decided_by", "decision_note", "created_at")}})
            return self.get(a.id)

    def approve(self, alert_id: str, officer: str, note: str | None = None) -> Alert:
        return self._decide("approved", alert_id, officer, note)

    def reject(self, alert_id: str, officer: str, reason: str) -> Alert:
        if not reason or not reason.strip():
            raise AlertError("a reason is required to reject an alert")
        return self._decide("rejected", alert_id, officer, reason)

    def _decide(self, kind: str, alert_id: str, officer: str, note: str | None) -> Alert:
        if not officer or not officer.strip():
            raise AlertError("a named officer is required")
        with self._lock():                      # re-read inside the lock: no stale decisions
            a = self.get(alert_id)
            if a.status != "pending":
                raise AlertError(f"alert {a.id} is already '{a.status}'")
            self._append({"event": kind, "alert_id": a.id, "officer": officer.strip(),
                          "note": note.strip() if note else None})
            return self.get(a.id)

    def release(self, alert_id: str, out_dir: str, released_by: str) -> str:
        """Publish the message for an approved alert. `released_by` is who pressed release (may differ from the approver)."""
        if not released_by or not released_by.strip():
            raise AlertError("a named officer is required to release an alert")
        released_by = released_by.strip()
        with self._lock():
            a = self.get(alert_id)
            if a.status != "approved":
                raise AlertError(f"alert {a.id} is '{a.status}'; only an approved alert can be released")
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"alert_{a.id}.txt")
            top = ", ".join(f"{n} ({c:+.0f})" for n, c in a.drivers[:3]) or "n/a"
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(f"A&E PRESSURE ALERT ({a.risk.upper()})\n"
                        f"Site: {a.site}\nWeek ending: {a.target_week}\n"
                        f"Forecast attendances: {a.forecast:.0f}\nMain drivers: {top}\n"
                        f"Approved by: {a.decided_by}\nReleased by: {released_by}\n"
                        f"Decision support only: a forecast, not a diagnosis or a causal claim.\n")
            try:
                self._append({"event": "released", "alert_id": a.id, "officer": a.decided_by, "released_by": released_by,
                              "file": path})
            except Exception:
                os.remove(tmp)                  # nothing is published unless the release is logged
                raise
            os.replace(tmp, path)
            return path
