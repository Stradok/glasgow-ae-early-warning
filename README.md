# Weather, air quality and weekly A&E attendance in Glasgow

Honours project MHW225671 (student: Muhammad Ahmer Khalid). It asks whether weather and air-quality data improve one-week-ahead
forecasts of A&E attendance at Glasgow hospitals (QEUH, GRI, and RHC as a secondary site), and builds a prototype early-warning
tool in which a named officer approves every alert. Decision support only: not clinically validated, predictive not causal.

## What is here
| Folder | Contents |
|---|---|
| `analysis/` | Data pipeline, models (GAM, XGBoost), rolling-origin evaluation, robustness and forecast-weather experiments, figures, tables, 18 tests. **Start with `analysis/RESULTS.md`.** |
| `prototype/` | The early-warning tool: forecast, low/medium/high risk class, drivers, officer approval with a tamper-evident log; command line and a local web page with login and a guided tour. 97 tests. See `prototype/README.md`. |
| `report/` | Interim report (LaTeX, PDF, Word) and a draft results chapter for the final report. |
| `docs/` | Guides and status: **start with `docs/HANDOVER.md`** (taking over) or `docs/GETTING_STARTED.md` (running it). Index in `docs/README.md`. |

## Headline results (146 test weeks, 7 Jan 2024 to 18 Oct 2026; details and caveats in `analysis/RESULTS.md`)
- A GAM with weather beats repeating last week's attendance: 22.5% lower error at QEUH, 16.0% at GRI (Holm-corrected p < 0.001).
- Weather adds value over the same model without it at QEUH (12.9%, p < 0.001); at GRI the result is inconclusive (7.1%, p = 0.054).
- Temperature carries the gain; air quality, humidity and rain add nothing. It is an association, not a causal effect.
- With real archived forecast weather QEUH keeps the gain; GRI keeps only part of it.
- Alerts catch only about a third to a half of high-pressure weeks (wide intervals): a prompt for review, not a trigger.

## Quick start
Needs Linux or macOS, Python 3, and `make`. Full walkthrough with troubleshooting: `docs/GETTING_STARTED.md`.
```
make setup                          # 1. create the environment and install packages (about 3 minutes)
make guide                          # 2. checklist: what is ready, and the next step (make guide-demo: for the offline demo)
make adduser NAME="Your Name"       # 3. create an officer account (you choose the password)
make demo                           # 4. offline demo: open http://localhost:8000, sign in, take the tour
make test                           # 5. all tests and the number check (18 + 112 numbers + 97), about a minute
```
For real use: `make refresh` (pull the latest data, needs internet) then `make serve`. `make` on its own lists every command.
Without `make`, the plain commands are in `docs/GETTING_STARTED.md` and `prototype/README.md`.
Tested on Linux only; macOS should work; Windows is not supported (the audit log uses file locking from the Unix standard library).
To rebuild every result from the frozen data: `make reproduce` (about 10 minutes; it rewrites `analysis/results/`). Details: "Reproduce" in `analysis/RESULTS.md`.

## Data and attribution
- Attendance: Public Health Scotland, [Weekly A&E Activity and Waiting Times](https://www.opendata.nhs.scot/dataset/weekly-accident-and-emergency-activity-and-waiting-times).
  Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
  Aggregated hospital counts only; no patient-level data.
- Weather and air quality: [Open-Meteo.com](https://open-meteo.com/) (ERA5-Land, CAMS, forecast and Previous Runs APIs), licensed
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The free service is for non-commercial use only; review the terms before any operational use.
  Citation: Zippenfenig, P. (2023). Open-Meteo.com Weather API. Zenodo. https://doi.org/10.5281/ZENODO.7970649
- This is a student research prototype. It is not endorsed by Public Health Scotland or the NHS.
- Frozen analysis data are in `analysis/data/`; the prototype's live pulls go to `prototype/data/` (not committed).

## Before sharing this repository
- The report title page carries the student's name and ID: keep the repository **private** unless the student agrees otherwise.
- No licence has been chosen. Add one (or none) deliberately; the report and data have their own terms.
- `archive/` and `docs/admin/` (module papers, other students' sample reports, photos) are git-ignored on purpose.
