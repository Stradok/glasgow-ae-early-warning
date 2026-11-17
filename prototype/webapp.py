"""Local web interface for the early-warning prototype (requirements R2 to R4 in one place).

An officer logs in, sees the latest forecast with its drivers, and approves, rejects or releases alerts. The
decision is written to the same hash-chained audit log as the command line, under the NAME THE OFFICER LOGGED IN
WITH (the form cannot supply a different name).

Design (standard library only, no new dependency):
  * binds to 127.0.0.1 only and refuses requests whose Host header is not localhost (blocks DNS rebinding);
  * server-side sessions in memory, random token in an HttpOnly, SameSite=Strict cookie, 8 hours;
  * every state-changing request is a POST and carries a per-session CSRF token;
  * 5 wrong passwords for a name lock that name for 60 seconds;
  * every value is HTML-escaped; a strict Content-Security-Policy is sent;
  * decisions go through alerts.AlertLog, so all approval rules and the integrity check still apply.
Limits: plain HTTP to localhost (do not expose the port), passwords are shared secrets kept in a local file, the
log file itself is only tamper-evident. A forecast run is synchronous and blocks that request for its duration.
"""
from __future__ import annotations

import hmac
import html
import os
import secrets
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import alerts as A
import ui
import users as U

SESSION_SECONDS = 8 * 3600
MAX_BODY = 8192
MAX_FAILS, LOCK_SECONDS = 5, 60
CSP = ("default-src 'none'; img-src data:; style-src 'unsafe-inline'; form-action 'self'; "
       "frame-ancestors 'none'; base-uri 'none'")


def csp(nonce: str | None) -> str:
    """Scripts run only with this response's nonce (the guided tour); pages without a nonce run no script at all."""
    return CSP + (f"; script-src 'nonce-{nonce}'" if nonce else "; script-src 'none'")


class App:
    """State shared by all requests."""

    def __init__(self, log: A.AlertLog, store: U.UserStore, demo: bool, backtest_week: str | None,
                 released_dir: str, tool):
        self.log, self.store, self.demo, self.backtest_week = log, store, demo, backtest_week
        self.released_dir, self.tool = released_dir, tool       # `tool` is the alert_tool module
        self.sessions: dict[str, dict] = {}
        self.fails: dict[str, list] = {}                         # name -> [count, locked_until]
        self.lock = threading.Lock()
        self.run_lock = threading.Lock()

    # ---- sessions
    def new_session(self, user: str) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            now = time.monotonic()
            self.sessions = {k: v for k, v in self.sessions.items() if v["exp"] > now}
            self.sessions[token] = {"user": user, "csrf": secrets.token_urlsafe(24), "exp": now + SESSION_SECONDS,
                                    "flash": []}
        return token

    def session(self, token: str | None) -> dict | None:
        with self.lock:
            s = self.sessions.get(token or "")
            if s and s["exp"] > time.monotonic():
                return s
            self.sessions.pop(token or "", None)
            return None

    def end_session(self, token: str | None) -> None:
        with self.lock:
            self.sessions.pop(token or "", None)

    # ---- flash messages (shown once, after the redirect)
    def flash(self, sess: dict, kind: str, msg: str) -> None:
        with self.lock:
            sess["flash"].append((kind, msg))

    def take_flash(self, sess: dict) -> list:
        with self.lock:
            out, sess["flash"] = sess["flash"], []
            return out

    # ---- login throttle
    @staticmethod
    def _key(name: str) -> str:
        return " ".join((name or "").split()).casefold()[:80]      # same normalisation as users.verify

    def begin_attempt(self, name: str) -> bool:
        """False if this name is locked. Otherwise count the attempt NOW, before the password is checked, so parallel
        guesses cannot all slip through; a correct login clears the count. MAX_FAILS attempts lock the name."""
        k, now = self._key(name), time.monotonic()
        with self.lock:
            f = self.fails.get(k)
            if f and f[1] > now:
                return False
            if f is None:
                if len(self.fails) >= 1000:                         # bounded memory: evict only names that are not locked
                    victim = next((n for n, v in self.fails.items() if v[1] <= now), None)
                    if victim is None:
                        return True                                 # every tracked name is locked; this one is not tracked
                    del self.fails[victim]
                f = self.fails[k] = [0, 0.0]
            f[0] += 1
            if f[0] >= MAX_FAILS:
                f[0], f[1] = 0, now + LOCK_SECONDS
            return True

    def login_ok(self, name: str) -> None:
        with self.lock:
            self.fails.pop(self._key(name), None)


# ---------------------------------------------------------------- page data
def render_dashboard(app: App, sess: dict, nonce: str) -> str:
    """Gather what the page needs (the log is read and verified here) and hand it to ui.dashboard."""
    try:
        alerts, events, intact, error = app.log.alerts(), app.log.events(), True, ""
    except A.AlertError as ex:
        alerts, events, intact, error = {}, [], False, str(ex)
    return ui.dashboard(nonce=nonce, user=sess["user"], csrf=sess["csrf"], flashes=app.take_flash(sess), demo=app.demo,
                        latest=app.tool.load_latest(app.demo), alerts=alerts, events=events, intact=intact, error=error)


# ---------------------------------------------------------------- handler
def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AEPrototype"
        sys_version = ""
        timeout = 10                                             # a stalled client cannot hold a thread for ever

        def log_message(self, fmt, *args):                       # keep the terminal quiet
            pass

        # -- plumbing
        def _send(self, code: int, body: str = "", headers: dict | None = None, ctype: str = "text/html; charset=utf-8",
                  nonce: str | None = None):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", csp(nonce))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _html(self, code: int, render):
            """Send a page; `render(nonce)` builds it with a fresh per-response script nonce."""
            nonce = secrets.token_urlsafe(16)
            self._send(code, render(nonce), nonce=nonce)

        def _login_page(self, code: int, error: str = ""):
            """The sign-in page runs no script, so it gets no nonce and a script-src 'none' policy."""
            self._send(code, ui.login_page("", app.demo, app.store.any_users(), error))

        def _redirect(self, where: str, headers: dict | None = None):
            self._send(303, "", {"Location": where, **(headers or {})})

        def _host_ok(self) -> bool:
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _token(self) -> str | None:
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie", ""))
            except Exception:
                return None
            return c["session"].value if "session" in c else None

        def _form(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 <= n <= MAX_BODY:
                raise ValueError("request too large")
            q = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"), keep_blank_values=True)
            return {k: v[0] for k, v in q.items()}

        def _guard(self):
            """Common checks. Returns False (after answering) when the request must not continue."""
            if not self._host_ok():
                self._send(400, "bad host")
                return False
            return True

        # -- routes
        def do_GET(self):
            if not self._guard():
                return
            tok = self._token()
            sess = app.session(tok)
            if self.path == "/login":
                return self._redirect("/") if sess else self._login_page(200)
            if self.path != "/":
                return self._send(404, "not found")
            if not sess:
                return self._redirect("/login")
            self._html(200, lambda n: render_dashboard(app, sess, n))

        def do_POST(self):
            if not self._guard():
                return
            try:
                form = self._form()
            except ValueError:
                return self._send(413, "request too large")
            tok = self._token()
            if self.path == "/login":
                return self._login(form)
            sess = app.session(tok)
            if not sess:
                return self._redirect("/login")
            if not hmac.compare_digest(form.get("csrf", "").encode("utf-8"), sess["csrf"].encode("utf-8")):
                return self._send(403, "bad or missing CSRF token")
            if self.path == "/logout":
                app.end_session(tok)
                return self._redirect("/login", {"Set-Cookie": "session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict"})
            if self.path == "/decide":
                self._decide(sess, form)
            elif self.path == "/run":
                self._run(sess, form)
            else:
                return self._send(404, "not found")
            self._redirect("/")

        def _login(self, form: dict):
            name, pw = form.get("name", "")[:80], form.get("password", "")[:200]
            if not app.begin_attempt(name):
                return self._login_page(429, "Too many wrong attempts for that name. Wait a minute.")
            who = app.store.verify(name, pw)
            if not who:
                return self._login_page(401, "Wrong name or password.")
            app.login_ok(name)
            token = app.new_session(who)
            self._redirect("/", {"Set-Cookie": f"session={token}; Max-Age={SESSION_SECONDS}; Path=/; HttpOnly; SameSite=Strict"})

        def _decide(self, sess: dict, form: dict):
            user, aid, action, note = sess["user"], form.get("id", ""), form.get("action", ""), form.get("note", "")[:500]
            try:
                if action == "approve":
                    a = app.log.approve(aid, user, note or None)
                    msg = f"Alert {a.id} ({a.site}) approved by {user}. Press 'Release message' to publish it."
                elif action == "reject":
                    a = app.log.reject(aid, user, note)
                    msg = f"Alert {a.id} ({a.site}) rejected by {user}."
                elif action == "release":
                    path = app.log.release(aid, app.released_dir, user)
                    msg = f"Released by {user}: {path}"
                else:
                    raise A.AlertError("unknown action")
                app.flash(sess, "ok", msg)
            except A.AlertError as ex:
                app.flash(sess, "err", f"Refused: {ex}")

        def _run(self, sess: dict, form: dict):
            if not app.run_lock.acquire(blocking=False):
                app.flash(sess, "err", "A forecast run is already in progress.")
                return
            try:
                T, notes = app.tool, []
                if form.get("refresh") == "1" and not app.demo:
                    T.D.refresh_history()
                res = T.compute_forecast(None, app.backtest_week if app.demo else None, app.log, say=notes.append)
                T.save_latest(res, app.demo)
                T.write_html(res, app.log, T.report_path(res[0]["target_week"], app.demo))
                app.flash(sess, "ok", f"Forecast for the week ending {res[0]['target_week']} computed. " + " ".join(notes))
            except (ValueError, A.AlertError) as ex:
                app.flash(sess, "err", f"Could not forecast: {ex}")
            except Exception as ex:                                  # network, data or library failure: report, do not crash
                app.flash(sess, "err", f"Forecast failed ({type(ex).__name__}): {str(ex)[:200]}")
            finally:
                app.run_lock.release()

    return Handler


class Server(ThreadingHTTPServer):
    request_queue_size = 64


def make_server(app: App, port: int = 8000) -> ThreadingHTTPServer:
    return Server(("127.0.0.1", port), make_handler(app))


def build_app(tool, demo: bool, backtest_week: str | None) -> App:
    """Wire the app to the demo or the real log, accounts and output folders (the demo can never touch the real ones)."""
    log = A.AlertLog(tool.LOG_DEMO if demo else tool.LOG)
    return App(log, tool.user_store(), demo, backtest_week,
               os.path.join(tool.OUT, "released_demo" if demo else "released"), tool)


def serve(tool, demo: bool, port: int, backtest_week: str | None) -> None:
    app = build_app(tool, demo, backtest_week)
    srv = make_server(app, port)
    print(f"Open http://localhost:{srv.server_address[1]}  (this computer only; Ctrl+C to stop)"
          + ("   [DEMO MODE]" if demo else ""))
    if not app.store.any_users():
        print('No officer accounts yet. In another terminal: python alert_tool.py adduser "Your Name"')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
