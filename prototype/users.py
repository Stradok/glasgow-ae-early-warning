"""Officer accounts for the approval step (requirement R4).

A name and a password per officer, stored as a salted scrypt hash (standard library only) in a JSON file.
The name an officer logs in with is the name written to the audit log, so a decision can no longer be
attributed to someone who did not log in.

Limits (a prototype, not a security product): passwords travel over plain HTTP to localhost only; anyone with
access to the machine's files can still edit the accounts file or the log; there is no password reset or
two-factor step.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets

N, R, P = 2 ** 14, 8, 1          # scrypt cost: about 16 MB and a few tens of milliseconds
MIN_PASSWORD = 10
MAX_PASSWORD = 200               # the web login accepts at most this many characters


class UserError(Exception):
    """Raised for an invalid name or password, or a duplicate account."""


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=32)


def clean_name(name: str) -> str:
    name = " ".join((name or "").split())
    if not 2 <= len(name) <= 40 or not name.isprintable():
        raise UserError("the officer name must be 2 to 40 printable characters")
    return name


class UserStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    @contextlib.contextmanager
    def _lock(self):
        with open(self.path + ".lock", "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def any_users(self) -> bool:
        return bool(self._read())

    def names(self) -> list[str]:
        return sorted(v["name"] for v in self._read().values())

    def add(self, name: str, password: str) -> str:
        name = clean_name(name)
        if not MIN_PASSWORD <= len(password or "") <= MAX_PASSWORD:
            raise UserError(f"the password must be {MIN_PASSWORD} to {MAX_PASSWORD} characters")
        with self._lock():
            users = self._read()
            if name.casefold() in users:
                raise UserError(f"an officer called '{name}' already exists")
            salt = secrets.token_bytes(16)
            users[name.casefold()] = {"name": name, "salt": salt.hex(), "hash": _hash(password, salt).hex()}
            tmp = self.path + ".tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=1)
            os.replace(tmp, self.path)
        return name

    def verify(self, name: str, password: str) -> str | None:
        """The officer's stored name if the password is right, else None. Unknown names cost the same time."""
        rec = self._read().get(" ".join((name or "").split()).casefold())
        salt = bytes.fromhex(rec["salt"]) if rec else b"\0" * 16
        got = _hash(password or "", salt)
        ok = hmac.compare_digest(got, bytes.fromhex(rec["hash"]) if rec else b"\0" * 32)
        return rec["name"] if rec and ok else None
