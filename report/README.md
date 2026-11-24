# Report folder

## Files
- `main.tex`, `references.bib`, `images/`: the **interim report** (LaTeX, module template). `main.pdf` is its build (19 pages, 0 errors with latexmk).
- `Interim_Report.docx`: a Word export of the same content (generated from the LaTeX; not opened in Word by the author of the script).
- `final_report_PLAN.md`: structure, marks and word budget for the **final report** (about 10,000 words, six chapters), taken from the 2026-27 guidance and marking scheme. No report text.
- `final/main.tex`: compilable skeleton of the final report (front page with the new SDG field, six chapter headings, `TODO` comments with the source files for each). Build: `cd final && latexmk -pdf main.tex`.
- `final_report_results_DRAFT.tex`: draft Results, Discussion and Conclusion for the **final report** (due 9 Apr 2027). A base to rewrite
  in the student's own words, not final text. Every number comes from `../analysis/results/results_tables.md`.
- `sources_verification.md`: links, quality grades and what was checked for each source (abstracts only; full texts not yet read).
- `RUBRIC_CHECK.md`, `check_report.py`: requirement-by-requirement cross-check (`python3 check_report.py main.pdf --rubric RUBRIC_CHECK.md`).
- Older previews, backups and the module zips are in `../archive/` (not part of the build).

## Build
```
sudo apt install -y texlive-latex-recommended texlive-latex-extra texlive-bibtex-extra texlive-fonts-recommended biber latexmk
cd report && latexmk -pdf -interaction=nonstopmode main.tex
```
Overleaf's free plan may time out; a local build has no limit.

## Fill in before submitting (top of `main.tex`)
- `\supervisor`, `\secondmarker` (placeholders), `\degree`, the signature line and date, and the year (the RSPI paper says Year 3, the deadline list Year 4).
- `\wordcount`: currently "approx. 3830" (citations uncounted); counting each in-text citation as about three words gives about 4,000. Confirm with texcount or Overleaf.

## Before you hand anything in
- Read the full text of Murtas 2022 (base paper), Marcilio 2013, Vollmer 2021, Blanco 2026, Corcuera Hotz 2020, Wan 2022, Garcia Crespi 2026. The claims so far rest on abstracts and publisher pages.
- Confirm with the supervisor: Murtas as base paper, whether ethics screening is needed for open aggregated data, and the practical threshold for H1.
- Check the university's rules on AI-assisted writing. The declaration says the work is the student's own; write the final text yourself.
