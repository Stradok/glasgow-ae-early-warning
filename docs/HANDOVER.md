# Handover: read this first

For the teammate who will take over the documentation. The code and analysis are finished and tested. What remains is
mostly writing, sign-offs, and things only the student can do. Date of this note: 17 November 2026.

## 1. Get running (15 minutes)

1. Follow [GETTING_STARTED.md](GETTING_STARTED.md). `make setup`, `make guide`, `make test`, then `make demo`.
2. You should see `18 passed`, `112 / 112 numbers confirmed` and `97 passed`. If you do not, stop and tell the student.
3. Take the in-app tour, then read [ARCHITECTURE.md](ARCHITECTURE.md).

## 2. What is finished

| Part | Where | Evidence |
|---|---|---|
| Data pipeline, models, evaluation, robustness, alert evaluation | `analysis/` | 18 tests; `check_results.py` confirms 112 quoted numbers |
| Results write-up with every caveat | `analysis/RESULTS.md` | Generated tables in `analysis/results/` |
| Early-warning prototype (command line and web page, login, approval, audit log, guided tour) | `prototype/` | 97 tests; the web page was checked by hand in a browser on 15 November (the later credits footer was checked in the served HTML only) |
| Interim report (submitted or about to be: ask the student) | `report/main.pdf`, `report/Interim_Report.docx` | Built with LaTeX |
| Draft results chapter for the final report | `report/final_report_results_DRAFT.tex` | About 1,300 words, not rebuilt since its last edit |
| Ethics evidence for the public data | `ethics_evidence.md` | Links opened on 16 November 2026 |
| Progress report for partners | `progress_report.pdf` | Source: `progress_report.tex` |

## 3. What is not finished (the documentation work)

Ordered by deadline. Dates are 2026-27 module dates: initial prototype 27 Nov 2026, final report 9 Apr 2027 (3pm),
recorded presentation 15 Apr 2027 (3pm).

| # | Task | Notes |
|---|---|---|
| 1 | Prototype hand-in and demo | The student must run it, understand it, and demo it. You can help rehearse using `make demo`. |
| 2 | Final report, 4,000 words | Contents, figures, tables, references and appendices are not counted. Only the results chapter has a draft. |
| 3 | Update the report's introduction, literature and methods | List below. |
| 4 | Read the key papers in full | So far only abstracts were read. See `report/sources_verification.md`. |
| 5 | Recorded presentation | Not started. Figures are in `analysis/figures/`. |
| 6 | Tidy the README and docs for the repository | Optional polish, once the above is done. |

**Facts in the interim report that are now out of date** (update them in the final report):
- Hot and cold weeks are defined from the percentiles of pre-2024 data (18.3 °C and −0.7 °C), not from a GAM.
- Bank holidays follow the Scottish calendar.
- The XGBoost forecast is the mean of three runs.
- Extra models exist: M3a (XGBoost without weather) and the ablation models.
- The forecast-weather test covers 135 weeks from March 2024, not "2022 to 2026".
- The tool uses the temperature-only model M2t, which was chosen after seeing results. The report must say this.
- Evaluation models use the observed weather of the target week (a "nowcast"); the forecast-weather test addresses this.

## 4. Rules that matter

1. **Check the university's rules on AI-assisted writing before writing or pasting anything into the report.** Part of the
   code, analysis and draft text in this repository was produced with AI assistance. The report's declaration says the
   work is the student's own. The student must read the policy and disclose as it requires. Do not paste
   draft text into the final report unread; rewrite it in the student's own words and make sure the student can explain it.
2. **Numbers come from the files, not from memory.** Every number in `RESULTS.md` is checked by `check_results.py`. If you
   quote a number in a document, find it in `analysis/results/results_tables.md` first. Run `make test` after any change.
3. **Do not re-run the experiments casually.** `make reproduce` rewrites `analysis/results/` and can change numbers. The report
   would then no longer match. Ask first.
4. **Keep the repository private** while the report carries the student's name and ID. Do not commit `archive/`,
   `docs/admin/`, `prototype/accounts/`, `prototype/output/` or `prototype/data/`. The `.gitignore` already excludes them.
5. **Supervisor sign-offs are still missing.** Nothing has been approved by the supervisor yet: the topic change, the
   base paper (Murtas et al., 2022, provisional), the hypotheses and the 15% practical target, and the ethics position.
   See `PROJECT_STATUS.md`.

## 5. Ethics

An email from a lecturer (16 November 2026) says the ethics form stays open, that public data needs evidence that its terms
allow the use and that it is anonymised or aggregated, and that the interim report does not bind the project to everything
stated in it. The evidence is in [ethics_evidence.md](ethics_evidence.md). The student has to submit the application.

## 6. Known gaps in the code (be honest about them in documents)

- Linux and macOS only. Not tested on macOS or Windows.
- Nobody except the developer has run it. No hospital staff have tried it.
- Alerts catch about a third to a half of high-pressure weeks. At GRI the weather gain is inconclusive and falls to 13.2% with
  forecast weather, below the 15% target.
- Plain HTTP on localhost, no password reset, not clinically validated.
- No licence has been chosen for the code. Choose one deliberately, or none.
- There is no automated build service (CI), because one could not be tested here.

## 7. Where everything is

| Path | What |
|---|---|
| `README.md` | Overview and quick start |
| `Makefile` | Short commands (`make` lists them) |
| `CLAUDE.md` | Instructions that Claude Code reads automatically: set-up steps and the rules |
| `docs/` | This folder: guides, status, ethics evidence, progress report |
| `analysis/` | The study. Start with `RESULTS.md` |
| `prototype/` | The tool. See `README.md` there |
| `report/` | Interim report, final-report draft, references, checks |
| `archive/`, `docs/admin/` | Local only, git-ignored: module papers and old material |
