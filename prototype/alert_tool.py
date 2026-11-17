#!/usr/bin/env python3
"""A&E pressure early-warning prototype for Glasgow (QEUH, GRI, RHC).

Requirements (report Section 3.2.4)
  R1  fetch the latest attendance and weather forecast          -> `refresh`, `forecast`
  R2  one-week forecast and a low / medium / high risk class      -> `forecast`
  R3  show the main drivers                                       -> `forecast` (table and HTML page)
  R4  an officer approves every alert, with a log                 -> `pending`, `approve`, `reject`, `release`, `log`

Decision support only: forecasts are predictive, not causal, and nothing is released without a named officer.

Examples (from the prototype/ folder, after `. ../analysis/.venv/bin/activate`):
  python alert_tool.py forecast --backtest-week 2026-10-18   # offline demo; writes to the demo log only
  ../analysis/.venv/bin/python alert_tool.py refresh                               # pull the latest data
  ../analysis/.venv/bin/python alert_tool.py forecast                              # live forecast
  ../analysis/.venv/bin/python alert_tool.py pending
  ../analysis/.venv/bin/python alert_tool.py approve <id> --officer "A. Officer"
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import errno
import html
import io
import json
import math
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alerts as A  # noqa: E402
import users as U  # noqa: E402
import data_access as D  # noqa: E402
import engine as E  # noqa: E402

OUT = os.path.join(HERE, "output")
LOG = os.path.join(OUT, "alert_log.jsonl")
LOG_DEMO = os.path.join(OUT, "alert_log_demo.jsonl")   # offline demo runs never touch the real log
USERS = os.path.join(HERE, "accounts", "users.json")   # officer accounts (salted scrypt hashes); kept out of output/ so clearing output/ cannot disable them
SITE_NAMES = {"QEUH": "Queen Elizabeth University Hospital", "GRI": "Glasgow Royal Infirmary",
              "RHC": "Royal Hospital for Children"}


def backtest_days(daily: pd.DataFrame, week_ending: pd.Timestamp) -> pd.DataFrame:
    """Offline demo: treat the observed weather of a past week as if it had been forecast."""
    start = week_ending - pd.Timedelta(days=6)
    wk = daily[(daily["date"] >= start) & (daily["date"] <= week_ending)].copy()
    wk["tmean"] = (wk["tmax"] + wk["tmin"]) / 2        # the raw daily file keeps max/min only
    return wk.reset_index(drop=True)


def chart_b64(res: dict) -> str:
    from matplotlib.figure import Figure         # not pyplot: its global state is not thread-safe (the web app is threaded)
    h = res["history"]
    fig = Figure(figsize=(6.2, 2.4), dpi=110)
    ax = fig.subplots()
    ax.plot(range(-len(h) + 1, 1), h, color="#0072B2", lw=1.6, label="weekly attendance")
    ax.plot([0, 1], [h[-1], res["forecast"]], color="#D55E00", lw=1.6, ls="--")
    ax.scatter([1], [res["forecast"]], color="#D55E00", zorder=3, label="forecast")
    ax.axhline(res["p75"], color="#999999", lw=0.8, ls=":")
    ax.axhline(res["p90"], color="#999999", lw=0.8, ls=":")
    ax.text(-len(h) + 1, res["p90"], " 90th percentile", va="bottom", fontsize=7, color="#555")
    ax.text(-len(h) + 1, res["p75"], " 75th percentile", va="bottom", fontsize=7, color="#555")
    ax.set_xlabel("weeks relative to last observed week", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=7, loc="lower left", frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    return base64.b64encode(buf.getvalue()).decode()


PAGE_CSS = ("body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#222}"
            "table{border-collapse:collapse}td,th{padding:.25rem .6rem;border-bottom:1px solid #ddd;text-align:left}"
            ".card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}"
            ".tag{color:#fff;padding:.1rem .5rem;border-radius:4px;font-weight:600}")


def cards_html(results: list[dict], alerts: dict) -> str:
    """One card per hospital: risk class, forecast, chart, drivers and alert status (shared by the file and the web app)."""
    colours = {"low": "#009E73", "medium": "#E69F00", "high": "#D55E00"}
    parts = []
    for r in results:
        al = next((a for a in alerts.values() if a.site == r["site"] and a.target_week == r["target_week"]), None)
        status = (f"alert {html.escape(al.id)}: <b>{html.escape(al.status)}</b>" if al else
                  "watch only: no alert is raised for this tier" if r["risk"] == "medium" else "no alert")
        drivers = "".join(f"<tr><td>{html.escape(n)}</td><td>{c:+.0f}</td></tr>" for n, c in r["drivers"])
        parts.append(
            f"<div class='card'><h2>{SITE_NAMES[r['site']]} ({r['site']})</h2>"
            f"<p><span class='tag' style='background:{colours[r['risk']]}'>{r['risk'].upper()}</span> "
            f"forecast <b>{r['forecast']:.0f}</b> attendances (last week {r['last_week']:.0f}); "
            f"medium above {r['p75']:.0f}, high above {r['p90']:.0f} (previous 52 weeks). {status}.</p>"
            f"<img alt='chart' src='data:image/png;base64,{chart_b64(r)}'>"
            f"<h3>Main drivers (effect on the forecast vs a typical week)</h3>"
            f"<table><tr><th>Driver</th><th>Attendances</th></tr>{drivers}</table></div>")
    return "\n".join(parts)


def write_html(results: list[dict], log: A.AlertLog, path: str) -> None:
    head = ("<!doctype html><meta charset='utf-8'><title>A&E pressure forecast</title>"
            f"<style>{PAGE_CSS}</style>"
            f"<h1>A&amp;E pressure forecast: week ending {results[0]['target_week']}</h1>"
            "<p>Decision support only. The forecast is predictive, not causal, and an alert is released only after a "
            "named officer approves it.</p>")
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n" + cards_html(results, log.alerts()))


def report_path(target_week: str, demo: bool) -> str:
    return os.path.join(OUT, f"forecast_demo_{target_week}.html" if demo else f"forecast_{target_week}.html")


def latest_path(demo: bool) -> str:
    return os.path.join(OUT, "latest_forecast_demo.json" if demo else "latest_forecast.json")


def save_latest(results: list[dict], demo: bool) -> None:
    """Keep the newest forecast so the web app can show it without recomputing."""
    os.makedirs(OUT, exist_ok=True)
    rows = [{**r, "history": [float(x) for x in r["history"]]} for r in results]
    tmp = latest_path(demo) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"saved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "results": rows}, f)
    os.replace(tmp, latest_path(demo))


def valid_result(r) -> bool:
    """A saved forecast record the page can safely draw: every field present, finite numbers, a known risk class and site."""
    try:
        needed = {"site", "target_week", "forecast", "risk", "last_week", "p75", "p90", "drivers", "history"}
        if not isinstance(r, dict) or not needed <= set(r) or r["risk"] not in ("low", "medium", "high") or r["site"] not in SITE_NAMES:
            return False
        if not isinstance(r["history"], list) or len(r["history"]) < 2 or not isinstance(r["drivers"], list):
            return False
        if not all(isinstance(d, (list, tuple)) and len(d) == 2 and isinstance(d[0], str) for d in r["drivers"]):
            return False
        nums = [r["forecast"], r["last_week"], r["p75"], r["p90"], *r["history"], *[d[1] for d in r["drivers"]]]
        return all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in nums)
    except (TypeError, KeyError, ValueError):
        return False


def load_latest(demo: bool) -> dict | None:
    """The saved forecast, or None (shown as 'no forecast yet') if the file is missing, corrupt or has any unusable record."""
    try:
        with open(latest_path(demo), encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("results"), list) and d["results"] and all(valid_result(r) for r in d["results"]):
            return d
    except (FileNotFoundError, ValueError, AttributeError, OSError):
        pass
    return None


def log_for(a) -> A.AlertLog:
    """The real log, or the demo log when --demo is given (backtest runs always use the demo log)."""
    return A.AlertLog(LOG_DEMO if getattr(a, "demo", False) or getattr(a, "backtest_week", None) else LOG)


def user_store() -> U.UserStore:
    return U.UserStore(USERS)


def cmd_adduser(a):
    import getpass
    if user_store().any_users():           # once accounts exist, only an existing officer can add another
        who = input("an existing officer's name (to authorise this): ")
        print("authorised by", verified_officer(who))
    pw = getpass.getpass("password (at least 10 characters): ")
    if pw != getpass.getpass("repeat the password: "):
        sys.exit("the two passwords differ; nothing was saved")
    print("created officer account:", user_store().add(a.name, pw))


def guide_steps(demo: bool = False) -> list[tuple[bool, str, str]]:
    """Read-only start-up checks: (done, what, command to run when not done). Never changes any file."""
    import importlib.util
    missing = [m for m in ("numpy", "pandas", "scipy", "pygam", "matplotlib", "holidays") if importlib.util.find_spec(m) is None]
    frozen = os.path.isfile(os.path.join(HERE, "..", "analysis", "data", "weekly_dataset.csv"))
    try:
        live = os.path.isdir(D.DATA) and any(n.endswith(".json") or n.endswith(".csv") for n in os.listdir(D.DATA))
        accounts = os.path.isfile(USERS) and user_store().any_users()      # opening a store would create its folder
    except (OSError, ValueError):          # a diagnostics command reports a damaged file as "not ready", never a traceback
        live, accounts = False, False
    latest = load_latest(demo) is not None
    log_file = LOG_DEMO if demo else LOG
    try:
        waiting = sum(1 for al in A.AlertLog(log_file).alerts().values() if al.status == "pending") if os.path.isfile(log_file) else 0
    except Exception:                      # any damaged or odd log: say so rather than crash or guess
        waiting = -1                                   # log unreadable: say so rather than guess
    steps = [
        (not missing, "Python packages installed" + (f" (missing: {', '.join(missing)})" if missing else ""),
         "make setup    (or: pip install -r analysis/requirements.txt)"),
        (frozen, "Frozen analysis data present (analysis/data/weekly_dataset.csv)", "restore analysis/data/ from the repository"),
        (accounts, "At least one officer account exists", 'python alert_tool.py adduser "Your Name"'),
    ]
    if not demo:
        steps.append((live, "Live data pulled (prototype/data/)", "python alert_tool.py refresh    (about a minute; needs internet)"))
    steps.append((latest, "A forecast has been computed", "press 'Run forecast now' on the web page, or: python alert_tool.py "
                  + ("--demo serve" if demo else "forecast")))
    steps.append((waiting == 0, "No alerts waiting for a decision" if waiting >= 0 else "Alert log unreadable: run `python alert_tool.py log`",
                  "approve or reject them on the web page, or: python alert_tool.py pending"))
    return steps


def cmd_guide(a):
    print("Start-up guide" + (" (demo mode)" if a.demo else "") + ": what is ready and what to do next\n")
    steps = guide_steps(a.demo)
    for i, (ok, what, cmd) in enumerate(steps, 1):
        print(f"  {i}. [{'x' if ok else ' '}] {what}")
    todo = next(((what, cmd) for ok, what, cmd in steps if not ok), None)
    if todo:
        print(f"\nNext step: {todo[0]}\n    {todo[1]}")
    else:
        print("\nEverything is ready. Start the web page:\n    python alert_tool.py " + ("--demo " if a.demo else "") + "serve\n"
              "then open http://localhost:8000, sign in, and press 'Take the tour'.")
    print("\nTip: `python alert_tool.py --demo serve` runs the whole tool offline with a past week, which is the safest way to try it.")


def cmd_serve(a):
    import webapp
    try:
        webapp.serve(sys.modules[__name__], a.demo, a.port, a.backtest_week)
    except OSError as ex:
        if ex.errno not in (errno.EADDRINUSE, errno.EACCES):
            raise                          # not a port problem: do not blame the port
        nxt = a.port + 1 if a.port < 65535 else 8000
        sys.exit(f"cannot start the web page on port {a.port}: {ex.strerror}. Stop the other program, or choose another port: "
                 f"python alert_tool.py {'--demo ' if a.demo else ''}serve --port {nxt}")


def cmd_refresh(_):
    print("pulling attendance, weather and air quality (about a minute)...")
    print("wrote", D.refresh_history())


def compute_forecast(sites, backtest_week, log, say=print) -> list[dict]:
    """R1/R2/R3: load data, forecast each site, and open an alert for every "high" forecast.
    Used by both the command line and the web app. `say` receives notes for the user."""
    weekly, daily = D.load_history(), D.load_daily_weather()
    if backtest_week:
        target = pd.Timestamp(backtest_week)
        if target.weekday() != 6:
            raise ValueError("--backtest-week must be a Sunday (a week-ending date)")
        weekly = weekly[weekly["week_ending"] < target]
        days = backtest_days(daily, target)
        daily = daily[daily["date"] < days["date"].min()]
        say(f"OFFLINE DEMO: forecasting week ending {target.date()} from data before it, "
            f"using that week's observed weather as the 'forecast'.")
    else:
        target = weekly["week_ending"].max() + pd.Timedelta(days=7)
        try:
            days = D.fetch_forecast_days(target.date())
        except Exception as ex:  # network or forecast not yet available
            raise ValueError(f"could not get the weather forecast: {ex}")
        if target.date() < dt.date.today():
            say(f"note: the target week ended {target.date()} but its attendance is not published yet, so its "
                f"weather comes from the model's most recent analysis rather than a forecast.")
    results = [E.forecast_site(site, weekly, daily, days) for site in (sites or E.F.SITES)]   # all or nothing
    for r in results:
        if r["risk"] == "high":          # only the evaluated "high" tier raises an alert needing approval
            log.create(r["site"], r["target_week"], r["forecast"], r["risk"], r["model"], r["drivers"])
    return results


def cmd_forecast(a):
    log = log_for(a)
    demo = log.path == LOG_DEMO
    results = compute_forecast(a.site, a.backtest_week, log)
    print(f"\nWeek ending {results[0]['target_week']}  (model {E.MODEL}: GAM, temperature-only)\n")
    print(f"{'site':5} {'forecast':>9} {'last wk':>8} {'risk':>7}  main drivers")
    for r in results:
        d = "; ".join(f"{n} {c:+.0f}" for n, c in r["drivers"][:3])
        print(f"{r['site']:5} {r['forecast']:9.0f} {r['last_week']:8.0f} {r['risk']:>7}  {d}")
    os.makedirs(OUT, exist_ok=True)
    path = report_path(results[0]["target_week"], demo)
    write_html(results, log, path)
    save_latest(results, demo)
    print(f"\nreport: {path}")
    print("alerts needing approval:", ", ".join(x.id for x in log.alerts().values() if x.status == "pending") or "none",
          "(demo log)" if demo else "")


def cmd_pending(a):
    rows = [x for x in log_for(a).alerts().values() if x.status == "pending"]
    if not rows:
        return print("no pending alerts")
    for x in rows:
        print(f"{x.id}  {x.site:5} week ending {x.target_week}  {x.risk:6} forecast {x.forecast:.0f}")


def verified_officer(name: str) -> str:
    """Once any officer account exists, a decision from the command line needs that officer's password too. This stops
    casual or accidental misattribution; it is not a defence against someone who can edit the files on this machine.
    With no accounts the name is unverified (and we say so)."""
    store = user_store()
    if not store.any_users():
        print("warning: no officer accounts exist, so this name is NOT verified. Create accounts with: adduser")
        return name
    import getpass
    who = store.verify(name, getpass.getpass(f"password for {name}: "))
    if not who:
        raise A.AlertError("wrong officer name or password")
    return who


def cmd_approve(a):
    x = log_for(a).approve(a.id, verified_officer(a.officer), a.note)
    print(f"approved {x.id} by {x.decided_by}")


def cmd_reject(a):
    x = log_for(a).reject(a.id, verified_officer(a.officer), a.reason)
    print(f"rejected {x.id} by {x.decided_by}: {x.decision_note}")


def cmd_release(a):
    log = log_for(a)
    out = os.path.join(OUT, "released_demo" if log.path == LOG_DEMO else "released")
    print("released ->", log.release(a.id, out, verified_officer(a.officer)))


def cmd_log(a):
    for e in log_for(a).events():
        print(e["ts"], e["event"], e.get("alert", {}).get("id") or e.get("alert_id"),
              e.get("officer", ""), e.get("note") or "")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", action="store_true", help="use the demo log (for the offline backtest demo)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh", help="R1: pull the latest attendance and weather").set_defaults(fn=cmd_refresh)
    f = sub.add_parser("forecast", help="R2/R3: forecast next week, classify risk, list drivers")
    f.add_argument("--site", action="append", choices=["QEUH", "GRI", "RHC"])
    f.add_argument("--backtest-week", help="offline demo: forecast this past week-ending date (a Sunday)")
    f.set_defaults(fn=cmd_forecast)
    sub.add_parser("pending", help="list alerts waiting for an officer").set_defaults(fn=cmd_pending)
    ap = sub.add_parser("approve", help="R4: approve an alert")
    ap.add_argument("id"); ap.add_argument("--officer", required=True); ap.add_argument("--note")
    ap.set_defaults(fn=cmd_approve)
    rj = sub.add_parser("reject", help="R4: reject an alert (reason required)")
    rj.add_argument("id"); rj.add_argument("--officer", required=True); rj.add_argument("--reason", required=True)
    rj.set_defaults(fn=cmd_reject)
    rl = sub.add_parser("release", help="release an APPROVED alert (writes the message file)")
    rl.add_argument("id"); rl.add_argument("--officer", required=True, help="who is releasing it (logged)")
    rl.set_defaults(fn=cmd_release)
    sub.add_parser("guide", help="check the set-up and say what to do next (changes nothing)").set_defaults(fn=cmd_guide)
    sub.add_parser("log", help="show the audit log").set_defaults(fn=cmd_log)
    au = sub.add_parser("adduser", help="create an officer account (asks for a password)")
    au.add_argument("name"); au.set_defaults(fn=cmd_adduser)
    sv = sub.add_parser("serve", help="start the local web interface (http://localhost:8000)")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--backtest-week", default="2026-10-18", help="demo mode only: the past week to forecast")
    sv.set_defaults(fn=cmd_serve)
    a = p.parse_args(argv)
    try:
        a.fn(a)
    except (A.AlertError, U.UserError) as ex:
        sys.exit(f"refused: {ex}")
    except ValueError as ex:
        sys.exit(f"cannot forecast: {ex}")


if __name__ == "__main__":
    main()
