# Project status (17 Nov 2026)

Honours project MHW225671: forecasting weekly A&E attendance in Glasgow from weather and air quality, with a
human-approved early-warning prototype. Student: Muhammad Ahmer Khalid.

| Deadline | Item | State |
|---|---|---|
| 6 Nov 2026 (passed) | Interim report | Written and built (`report/main.pdf`, `report/Interim_Report.docx`). Placeholders (supervisor, second marker, signature, date) are the student's to fill; submission to be confirmed with the student. |
| 27 Nov 2026 | Initial prototype | **Built and tested** (`prototype/`): command line plus a local web page with officer login. Needs the student to run it, understand it, and demo it. |
| 9 Apr 2027 | Final report | **Results, discussion and conclusion drafted** (`report/final_report_results_DRAFT.tex`, `analysis/RESULTS.md`). Introduction, literature review and methods carry over from the interim report; they need updating (see below). |
| 15 Apr 2027 | Recorded presentation | Not started. Figures in `analysis/figures/` are ready to use. |

## Taking over
Read `docs/HANDOVER.md` first, then `docs/GETTING_STARTED.md`.

## What exists
- `analysis/` data pipeline, models, rolling-origin evaluation, robustness checks, forecast-weather experiment, figures,
  generated tables, 18 tests (including no-look-ahead checks at 1, 2 and 4 weeks), and a script that checks every number quoted in `RESULTS.md`.
- `prototype/` forecast, risk class, drivers, and officer approval with a hash-chained, tamper-evident log. Run `python alert_tool.py adduser "Name"` then `python alert_tool.py serve` for the web page (login, approve/reject/release, audit log); the command line still works and asks for the officer's password once an account exists. 97 tests; independent reviews of the login code and of the UI, tour and repo layout were done and their findings fixed (the last fixes were verified by tests, not re-reviewed).
- An independent review of the code and claims was done; its findings were fixed (temperature-effect wording, alert claims, flag-rule look-ahead, log hardening, demo runs separated from the real log). Details in the changes to `analysis/RESULTS.md`.
- `prototype/output/` holds demo runs from development (git-ignored); delete it to start clean. Old dev runs, stale previews, zips and other students' sample reports are in `archive/` (git-ignored).
- `report/` interim report (LaTeX, PDF, Word) and the draft results chapter.

## Headline results (details and caveats in `analysis/RESULTS.md`)
- Beats last week's attendance: M2 reduces MAE by 22.5% (QEUH) and 16.0% (GRI); hypothesis H2 supported.
- Weather adds value over the same model without weather at QEUH (12.9%, Holm p < 0.001); GRI is inconclusive (7.1%, p = 0.054 plain, 0.024 with a Newey-West variance).
- Temperature carries the gain, mainly through the week-to-week change (about 10 attendances per degree of warming); air quality, humidity and rain add nothing; a last-year-weather placebo removes the gain. This is an association, not a causal effect.
- With real archived forecasts QEUH keeps the gain; GRI keeps part of it.
- Alerts catch only about a third to a half of high-pressure weeks (wide intervals): use as a prompt for review. The prototype alerts on the "high" tier only. This now holds for the prototype's own model M2t, real forecast weather and the medium tier too (`analysis/RESULTS.md`, Section 5b): the alert is about 2.4 to 4.5 times more precise than a random one, but its advantage over repeating last week is fewer false alarms at QEUH, not more catches; the medium tier is only modestly informative and stays watch-only.

## Decisions for the student and supervisor
1. Confirm the hypotheses are worded as intended and agree the practical threshold for H1 (the 15% target is met at QEUH and GRI with observed weather, at QEUH only with forecast weather).
2. Ethics. The Honours Ethics Guide (GCU Learn, read 24 Nov) lists analysis of anonymised public datasets and software built without participant testing as projects that do not normally need approval, but the "Does my project require Ethics Approval?" Decision Tool must still be completed (its outcome is saved to the Gradebook). If it says approval is required, the application form must be signed by the student and the supervisor. Ask the supervisor to confirm that using published NHS aggregate counts (no patients or staff recruited) is acceptable. Do not let anyone use the prototype as a test participant: user-testing a prototype does need approval. Evidence for the data terms and the aggregation is in `docs/ethics_evidence.md`; the final report must include proof of it. A lecturer's email (16 Nov) says the form stays open and that the interim report does not bind the project to everything stated in it.
3. Decide whether to keep the temperature-only model M2t for the prototype (it was chosen after the ablation, a post-hoc choice; M2 is the pre-specified model).
4. The final report is about 10,000 words (9,000 to 11,000; over 11,000 loses 10% of the mark), with six chapters. See `report/final_report_PLAN.md`. The draft results chapter is about 1,300 words.

## Before the final report
- Update the interim methods text: hot/cold thresholds are percentiles of pre-2024 data (not GAM-derived); bank holidays use the Scottish calendar; XGBoost forecasts are the mean of 3 seeds; M3a and the ablation models exist; weather-for-target-week caveat.
- Read the full texts of the key papers (only abstracts were checked), and add literature on infection confounding.
- Re-pull data near the final deadline if desired (`prototype/alert_tool.py refresh` writes to `prototype/data/`, not the frozen analysis data); re-running the experiments would change the numbers.
- Rewrite everything in the student's own words and check the university's AI-writing policy.
