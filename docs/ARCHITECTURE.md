# How the project is built and why

For someone who has not seen the code. It explains the parts, how data moves, and the main design choices, including
the alternatives that were rejected. For the numbers, read [../analysis/RESULTS.md](../analysis/RESULTS.md).

## The two halves

```
 Public Health Scotland (weekly A&E counts) ─┐
                                             ├─►  analysis/   study: does weather help a forecast?   ─► results, figures, report
 Open-Meteo (weather, air quality) ──────────┘          │
                                                        │  same model code (forecast_lib.py)
                                                        ▼
                                              prototype/   tool: forecast ► risk class ► officer approves ► released
```

| Half | Question it answers | Main files |
|---|---|---|
| `analysis/` | Does weather improve one-week-ahead forecasts of weekly attendance at QEUH, GRI and RHC? | `build_dataset.py`, `forecast_lib.py`, `run_experiments.py`, `robustness.py`, `forecast_weather_test.py`, `alerts_eval.py`, `RESULTS.md` |
| `prototype/` | Can the forecast be turned into an alert that a named person must approve? | `alert_tool.py`, `engine.py`, `alerts.py`, `users.py`, `webapp.py`, `ui.py`, `data_access.py` |

The prototype imports the analysis code instead of copying it, so the tool forecasts with exactly the model that was
evaluated. A test (`test_engine_features_match_analysis_build_features` in `prototype/tests/test_engine.py`) checks that the two build the same features.

## Analysis pipeline

1. **Data** (`build_dataset.py`): pulls attendance (Public Health Scotland open data API) and daily weather and air quality
   (Open-Meteo), aggregates to Monday-to-Sunday weeks, and writes `analysis/data/weekly_dataset.csv`. The dataset is frozen at
   18 October 2026 so that results can be reproduced.
2. **Features and models** (`forecast_lib.py`): lagged attendance, time of year, Scottish bank holidays, and weather. Models
   are baselines (B1 seasonal naive, B2 last week), a GAM without weather (M1), a GAM with weather (M2), a GAM with
   temperature only (M2t), and XGBoost with and without weather (M3, M3a).
3. **Evaluation** (`run_experiments.py`): rolling origin. For each of 146 test weeks the models are re-fitted using only
   earlier weeks, then forecast one week ahead. Tests compare models (Diebold-Mariano with Holm correction, plus a
   Newey-West check). `analysis/tests/` includes checks that no forecast can see the future.
4. **Robustness** (`robustness.py`, `forecast_weather_test.py`): which weather variable carries the gain, a placebo using
   last year's weather, and a test with real archived weather *forecasts* instead of observed weather.
5. **Alerts** (`alerts_eval.py`): how often a high-risk alert is right and how many high-pressure weeks it catches.
6. **Outputs**: `results/` (CSV files), `figures/`, and `RESULTS.md`. `check_results.py` recomputes every number quoted in
   `RESULTS.md` from the CSV files.

## Prototype

| Module | Job |
|---|---|
| `data_access.py` | Pulls and loads live data into `prototype/data/` (the frozen analysis data is never overwritten). |
| `engine.py` | Trains M2t on all published weeks, forecasts the next week, assigns the risk class, explains the drivers. |
| `alerts.py` | The approval rules and the audit log (append-only, each line hashed with the previous one). |
| `users.py` | Officer accounts: salted scrypt password hashes, file mode 600. |
| `webapp.py` | The local web server: login, sessions, CSRF protection, lockout, the pages. Standard library only. |
| `ui.py` | All page markup, styling and the guided tour. |
| `alert_tool.py` | The command line, and the glue between the other modules. |

**Risk class.** The forecast is compared with the 75th and 90th percentiles of the previous 52 weeks: above the 90th is High,
above the 75th is Medium, otherwise Low. Only High creates an alert, because only that tier was evaluated for alerting.

**Approval rules** (enforced in code, covered by tests): an alert starts pending. A decision needs a named, logged-in
officer. A rejection needs a reason and is final for that hospital and week. An alert is decided once. Only an approved alert
can be released, and the release is logged before the message file is written.

## Design choices and rejected alternatives

| Choice | Why | Rejected |
|---|---|---|
| Weekly counts, three hospitals | The open data supports it. Daily or condition-specific data is not public. | The original daily heat-illness proposal. |
| GAM as the tool's model | It shows each term's effect, which the tool needs to explain a forecast. It performed as well as XGBoost here. | XGBoost (harder to explain, no gain). |
| Temperature-only model (M2t) in the tool | The ablation showed temperature carries the gain, and a temperature forecast exists for next week. | The full weather model M2. **This choice was made after seeing results (post hoc) and the report must say so.** |
| Rolling-origin evaluation | It copies real use: forecast, then learn the truth, then forecast again. | A single train/test split. |
| Standard-library web server | No new dependencies to install or audit for a local prototype. | Flask or Django. |
| Hash-chained log | Makes casual tampering visible without a database. | A database (more moving parts). It does not stop a determined attacker, and the docs say so. |
| Local only (127.0.0.1) | A prototype with passwords over plain HTTP must not be reachable from a network. | Hosting it. |
| `make` plus a `guide` command | Short commands for a newcomer and a self-check that says what to do next. | A long README of manual steps. |

## Known limits (short list; the full list is in the prototype README)

- The effect of temperature is an association, not proof of cause. Infections such as flu are not in the model.
- At GRI the weather gain is inconclusive and weaker with forecast weather.
- Alerts catch about a third to a half of high-pressure weeks. Treat an alert as a prompt for a human to look.
- Linux and macOS only. Plain HTTP on localhost, no password reset, not clinically validated.
