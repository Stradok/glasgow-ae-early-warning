# A&E pressure early-warning prototype (initial prototype, due 27 Nov 2026)

A tool (command line **and a local web page**) that forecasts next week's A&E attendance at QEUH, GRI and RHC, classes the risk
as low / medium / high, shows what drives the forecast, and releases an alert **only after a logged-in officer approves it**.
Decision support only: the forecast is predictive, not causal.

| Requirement (report 3.2.4) | Where | Command |
|---|---|---|
| R1 fetch the latest attendance and weather forecast | `data_access.py` (reuses `analysis/build_dataset.py`) | `refresh`, `forecast` |
| R2 one-week forecast and low / medium / high class | `engine.py` | `forecast` |
| R3 show the main drivers | `engine.py` (GAM term effects), HTML page | `forecast` |
| R4 officer approval with a log | `alerts.py`, `users.py`, `webapp.py` | web page, or `pending`, `approve`, `reject`, `release`, `log` |

## Run it
From the repository root, `make guide` checks the set-up and names the next step, and `make demo` starts the offline demo (see `docs/GETTING_STARTED.md`). The plain commands:
```
cd prototype
. ../analysis/.venv/bin/activate          # create it first: see analysis/RESULTS.md, "Reproduce"
python alert_tool.py guide                                  # checklist: what is ready and the next step (changes nothing)
python alert_tool.py adduser "A. Officer"                   # asks for a password (10 to 200 characters); once any account exists, an existing officer must authorise it
python alert_tool.py serve                                  # web interface: open http://localhost:8000 and sign in
python alert_tool.py --demo serve                           # same, but offline: demo log and a past week as the 'forecast'
python alert_tool.py forecast --backtest-week 2026-10-18   # offline demo, no internet needed; uses a separate DEMO log
python alert_tool.py --demo pending                         # --demo makes pending/approve/reject/release/log use the demo log
python alert_tool.py refresh                                # R1: pull the latest data (about a minute)
python alert_tool.py forecast                               # live forecast for the week after the last published week
python alert_tool.py pending                                # alerts waiting for an officer
python alert_tool.py approve <id> --officer "A. Officer" --note "checked with site manager"   # asks for the password
python alert_tool.py reject  <id> --officer "A. Officer" --reason "forecast week affected by a known event"
python alert_tool.py release <id> --officer "A. Officer"    # works only for an approved alert; the releaser is logged too
python alert_tool.py log                                    # full audit trail
```
### The web page
Sign in, press **Run forecast now** (optionally pulling the latest data first), read the forecast cards (risk class, chart,
main drivers), then **Approve** or **Reject** (a reason is required) each pending alert, and **Release message** for an approved
one. The audit log and its integrity check are shown at the bottom. If the integrity check fails, decisions are refused.
The page has one card per hospital (risk label, forecast, 52-week chart with the 75th/90th percentile bands, driver bars), a decision panel and the audit log. **Take the tour** (top bar) is an 8-step guided walkthrough; it starts by itself on a first visit and can be skipped with Esc. Its text and styling live in `ui.py`.

Officer accounts live in `accounts/users.json` (salted scrypt hashes, file mode 600), outside `output/`, so clearing `output/` does not remove them.
The log records who approved or rejected an alert and, separately, who released it.

Outputs go to `output/`: `forecast_<week>.html` (chart, risk class, drivers, alert status),
`alert_log.jsonl` (append-only audit log), `released/alert_<id>.txt` (the message for an approved alert).
Demo runs write `forecast_demo_<week>.html`, `released_demo/` and `alert_log_demo.jsonl`, never the real ones. `output/` may hold files from earlier development runs (some with older names); it is git-ignored, and deleting it starts clean (accounts are kept).

## How it works
1. **Data (R1).** Attendance from Public Health Scotland open data; observed weather and air quality from Open-Meteo
   (ERA5-Land, CAMS); next-week weather from the Open-Meteo forecast API. History is stored in `prototype/data/`;
   the frozen dataset used for the report in `analysis/data/` is never overwritten.
2. **Model (R2).** The temperature-only GAM `M2t` from `analysis/forecast_lib.py`: last week's, two weeks ago and last year's
   attendance, time of year, bank holidays, and temperature terms. It is re-trained on all published weeks each time (takes seconds).
3. **Risk class.** The forecast is compared with the 75th and 90th percentiles of the previous 52 weeks:
   above the 90th = high, above the 75th = medium, otherwise low. **Only "high" creates an alert** (the tier that was evaluated);
   "medium" is shown as watch-only.
4. **Drivers (R3).** Each GAM term's effect on this week's forecast relative to a typical week, largest first.
5. **Approval (R4).** Rules enforced in code and covered by tests: an alert starts pending; a decision needs a named officer;
   a rejection needs a reason and is final for that site and week; an alert can be decided once, under a file lock; only an
   approved alert can be released, and the release is logged before the message file is published. The log is append-only and
   hash-chained: editing, reordering or removing a line in the middle is detected and the tool refuses to continue (removing the last lines, or rewriting the whole file with valid hashes, is NOT detected; it shows casual tampering, it cannot
   prevent it). **Who is the officer (`users.py`, `webapp.py`):** the web page logs the officer in and writes the name they logged
   in with (a form cannot supply another name); after the first `adduser`, `approve`, `reject` and `release` on the command line also ask for the
   password. With no accounts at all, the command line accepts any name and warns that it is unverified.
6. **Web interface.** Standard library only. Listens on 127.0.0.1 only and rejects other Host headers; session cookie is HttpOnly and
   SameSite=Strict; every change is a POST with a CSRF token; 5 wrong passwords lock a name for 60 seconds (so someone who can reach the port can also keep an officer locked out: a denial of service this prototype does not prevent); all text is escaped; a
   strict Content-Security-Policy is sent.

## Evidence for the model choice (from `analysis/RESULTS.md`)
Rolling-origin test, 146 weeks, one week ahead, observed weather: the temperature-only model M2t has MAE 54.9 (QEUH), 57.7 (GRI)
and 84.8 (RHC) against 70.6, 68.1 and 96.8 for last week, i.e. 22.3%, 15.3% and 12.4% better; with real archived forecasts
(135 weeks) M2t is 23.0%, 13.0% and 15.0% better than last week. M2t was chosen after an ablation showed temperature carries
the gain (a post-hoc choice; the pre-specified model M2 is within 0.2 to 1.5 MAE). Alerts were evaluated for M2t as well
(`analysis/RESULTS.md`, Section 5b). At QEUH the high-tier alert caught 33% of high-pressure weeks (95% interval 17% to 55%) with 0.12 false
alarms a month with observed weather, and 38% (21% to 59%) with 0.16 a month on real archived forecasts; at GRI it caught 41% to 46% with
0.33 to 0.45 false alarms a month, and showed no clear advantage over repeating last week. The medium tier was evaluated too: better than
chance but only modestly informative (QEUH precision 0.60 against a 37% base rate), so it stays watch-only. So
**treat an alert as a prompt for human review, not a certainty, and the absence of an alert as no guarantee.**

## Known limits
- Not a real-time evaluation: PHS publishes with a delay, so a live run may forecast with older attendance data and a longer weather lead time than the tested one-week set-up.
- The model is trained on reanalysis weather but fed forecast-API weather at run time (training/serving mismatch, quantified in the forecast-weather experiment).
- The offline `--backtest-week` demo approximates the daily mean temperature by (max+min)/2.
- Forecasts one week ahead only. The target must be the week directly after the last published attendance week.
  PHS publishes with a delay, so a live run may forecast a week that has just ended (the tool says so).
- All-cause weekly counts, one weather point for the city, no infection data, no local holidays or school terms.
- Open-Meteo is free for non-commercial use only; review the terms before any operational use.
- Not clinically validated.
- Security is that of a local prototype: plain HTTP on localhost (do not expose the port or run it on a shared machine), no password
  reset or two-factor login, and anyone who can edit the files on disk can edit the accounts and rewrite the (unkeyed) hash chain.
  The web page blocks a forecast run for its duration (about a minute with a data pull).
- Alert performance rests on 11 to 26 alerts per row, so its intervals are wide; at the adult hospitals an alert is a prompt for review, and the absence of one is no guarantee.

## Tests
```
cd prototype && python -m pytest tests     # 97 tests: approval rules, tamper detection, forged and duplicate events, locking, engine checks and feature parity with the analysis code, offline end-to-end run, accounts, the web app (login, lockout, CSRF, name from the session, escaping, tampered log, forecast run) against a real local server, the data credits on every page, and the start-up guide
```
