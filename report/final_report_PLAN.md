# Final report plan (structure only, no prose)

Source: "Honours Project Final Report Guidance 26_27" and the final-report marking scheme (both in the local `Finalreportinstructions/` folder, not in the repo).
This file is a plan. It contains no report text. The student writes the text, after checking the university's AI-writing policy (see `CLAUDE.md`).

## Hard requirements
- Due **9 Apr 2027, 3pm**. Body text **about 10,000 words (9,000 to 11,000)**. Over 11,000 words loses 10% of the mark. The earlier "4,000 words" in older docs is wrong (it was the interim limit).
- Body count excludes abstract, contents, figures, tables, references and appendices.
- Submit: the report, a Turnitin copy named `YourName_Final_Report_2627`, and the full code as a zip via Grade Centre (a GitHub link in the report is also allowed).
- Possible live demo to the supervisor and second marker before the poster event. The student plans and drives it.
- Check the Turnitin similarity score early and often. Plagiarism and AI rules: Honours Project Study Guide chapter 11 (not yet read).
- Front page (pro forma): title, name, programme, student ID, supervisor, second marker, word count, **aligned SDGs (new)**, signed declaration with date.

## Chapters, marks and word budget (target about 9,900)
| # | Chapter | Marks | Words | Where the material already is |
|---|---|---|---|---|
| - | Abstract (250 to 350 words, not counted) | 5 | 300 | Summary of everything below; write last |
| 1 | Introduction | in Execution/Evaluation | 1,000 | `report/main.tex` intro; must now say how far the question was answered |
| 2 | Literature and Technology Review (update, improvements flagged at the chapter start) | 10 | 1,600 | `report/main.tex`, `references.bib`, `sources_verification.md`; read the key papers in full first |
| 3 | Execution (the story: what, why, how, justified against the literature) | 45 | 3,400 | `docs/ARCHITECTURE.md`, `analysis/RESULTS.md`, `analysis/data_quality.md`, `prototype/README.md` |
| 4 | Evaluation and Discussion (discussion in every section) | 25 (with ch. 6) | 2,400 | `analysis/results/results_tables.md`, `report/final_report_results_DRAFT.tex`, `analysis/figures/` |
| 5 | Legal, Social, Ethical and Professional Issues (exact title; all four aspects) | 5 | 700 | `docs/ethics_evidence.md`, Decision Tool outcome, data licences |
| 6 | Conclusions and Further Work (critical self-analysis, limits, reflection) | (see ch. 4) | 800 | `docs/PROJECT_STATUS.md`, known gaps in `docs/HANDOVER.md` |
| - | References, Appendices (not counted) | 5 (format) | - | `references.bib`; ethics evidence; extra tables |

Marks: Execution 45, Evaluation/Discussion/Conclusion/Further Work 25, Literature update 10, Abstract 5, LSEP 5, Format 5, Supervisor effort 5.

## Facts the report must carry (from the project record)
- Update the interim facts listed in `docs/HANDOVER.md` section 3 (percentile-based hot/cold weeks, Scottish bank holidays, XGBoost mean of three runs, M3a, 135-week forecast-weather test, M2t chosen after seeing results, observed-weather "nowcast").
- State the limits plainly: not clinically validated, no staff trial, GRI weather gain inconclusive (7.1%, p = 0.054) and 13.2% with forecast weather, below the 15% target, association not cause.
- Disclose AI assistance as the university's policy requires.
- Include proof that the data terms allow the use and that the data is aggregated (ethics guide, question 7).

## Open decisions before writing
1. AI-writing policy (Study Guide chapter 11, Code of Student Conduct).
2. Ethics Decision Tool outcome, and the supervisor's view on the "NHS" exclusion.
3. Supervisor sign-offs listed in `docs/PROJECT_STATUS.md`.
4. SDGs to align to (suggest discussing with the supervisor).
5. Whether the final report is built in LaTeX (`report/`) or the Word template.
