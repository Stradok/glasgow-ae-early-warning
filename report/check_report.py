#!/usr/bin/env python3
"""Cross-check the interim report against the module requirements.

Usage (from the report/ folder, Python 3, standard library only):
    python3 check_report.py                       # source checks only (no PDF)
    python3 check_report.py main.pdf              # also finds the PAGE of each requirement in a built PDF
    python3 check_report.py main.pdf --rubric RUBRIC_CHECK.md   # also (re)writes the rubric file with real page numbers

Page lookup needs `pdftotext` (package poppler-utils). Without it the page column shows n/a.
Requirement sources: marking-scheme photo (Introduction 25, Literature 50), older Methods marking sheets,
the module LaTeX template, the Word pro forma, and examiner feedback on the sample reports.
"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "main.tex")
BIB = os.path.join(HERE, "references.bib")
QUAL = os.path.join(HERE, "..", "analysis", "data_quality.md")
LIMIT = 4000

# kind: present (all phrases must be found) | absent (none may be found) | count>=N (phrase occurs at least N times) | manual
# where: section / paragraph to look at in the report. note: honest caveat shown in the rubric.
REQS = [
 # ---- front matter (template + pro forma) ----
 ("F1","Front","Module code on cover (MHW225671, full-time)","Template",["MHW225671"],"present","Title page",""),
 ("F2","Front","Cover says Interim Report 2026-27","Pro forma",["INTERIM REPORT","2026-27"],"present","Title page","Template said 2025-26; corrected"),
 ("F3","Front","Project title","Pro forma",["Forecasting Weekly Accident and Emergency Attendance in Glasgow"],"present","Title page",""),
 ("F4","Front","Student name and matriculation/ID number","Pro forma",["S2354571"],"present","Title page","ID taken from the RSPI paper; confirm it is correct"),
 ("F5","Front","Degree / programme","Pro forma",["AI & Data Science"],"present","Title page","CONFIRM programme (pro forma offers three)"),
 ("F6","Front","Supervisor and second marker filled in (no placeholders)","Pro forma",["[Supervisor name]","[Second marker name]"],"absent","Title page","TO DO: names still placeholders"),
 ("F7","Front","Word count stated (excluding contents, figures, tables, references, appendices)","Pro forma",["Word Count","excluding contents pages"],"present","Title page","Confirm the number with texcount"),
 ("F8","Front","Originality declaration text","Pro forma",["my own original work"],"present","Title page",""),
 ("F9","Front","Signed-by-student line and date","Pro forma",["Signed by Student"],"present","Title page","Student must sign/date"),
 ("F11","Front","Title page fits on ONE page (contents start on page 2, no spill-over)","Layout (found in first build)",["Contents 1 Introduction"],"page2","Title page","A first build spilled the Name/Date block onto page 2"),
 ("F10","Front","Contents and list of tables","Template",["Contents 1 Introduction","List of Tables"],"present","Pages after title","Preview PDF has a contents list without page numbers"),
 # ---- introduction (25 marks) ----
 ("I1","Introduction (25)","Background and motivation, citing sources","Template; rubric",["attendances reached 25.6 million"],"present","1.1 Background and motivation, para 1",""),
 ("I2","Introduction (25)","Clear statement of the problem addressed","Rubric 1st band",["The problem statement is therefore"],"present","1.2, para 2 (last sentence)",""),
 ("I3","Introduction (25)","Well-supported, argued case for the problem","Rubric 1st band",["Whether weather actually improves ED forecasts is contested"],"present","1.2, para 1","Argued from conflicting evidence"),
 ("I4","Introduction (25)","Research gap stated, hedged and evidenced","Examiner feedback",["suggests the gap addressed here","Search log"],"present","1.2, para 2; Table 1 (search log)","Gap rests on focused searches, not a systematic review"),
 ("I5","Introduction (25)","Aim","Template",["The aim is to investigate whether weather"],"present","1.3, para 1",""),
 ("I6","Introduction (25)","Research question","Template; rubric",["to what extent can machine-learning models"],"present","1.3, para 2",""),
 ("I7","Introduction (25)","Clear, testable hypotheses (H1, H2 with test and threshold)","Rubric; examiner feedback",["hypotheses separate two claims","Diebold"],"present","1.3, para 3","Practical-importance threshold to be agreed with supervisor"),
 ("I8","Introduction (25)","Secondary objectives (research tasks)","Template",["secondary objectives are research tasks"],"present","1.4, first list",""),
 ("I9","Introduction (25)","Primary objectives (deliverables, incl. prototype 27 Nov)","Template",["primary objectives are the project"],"present","1.4, second list",""),
 ("I10","Introduction (25)","Scope and limitations","Examiner feedback",["Scope and structure of this report"],"present","1.5",""),
 ("I11","Introduction (25)","Introduction leads naturally to the review (objectives map 1:1 to 2.1-2.5)","Rubric",["Secondary objective 1: weather","Secondary objective 5: early warning"],"present","1.4 and 2.1-2.5",""),
 # ---- literature and technology review (50 marks) ----
 ("L1","Literature (50)","Subsections correspond to the secondary objectives","Template",["Secondary objective 1:","Secondary objective 2:","Secondary objective 3:","Secondary objective 4:","Secondary objective 5:"],"present","2.1 to 2.5",""),
 ("L2","Literature (50)","How sources were found is stated","Rubric (proper referencing)",["focused review, not a systematic one"],"present","2, opening paragraph",""),
 ("L3","Literature (50)","Critical discussion, not summary only","Rubric 1st band",["Critical discussion"],"count>=2","2.1 and 2.2, paragraphs headed Critical discussion","Critical analysis is the weakest-evidenced area; read the sources in full"),
 ("L4","Literature (50)","Conflicting evidence identified and discussed","Examiner feedback",["worse or similar forecasts than calendar variables alone","no clear relation between total admissions"],"present","2.1 para 1; 2.2 para 2",""),
 ("L5","Literature (50)","Base paper identified and the project differentiated from it","Student request",["adopted here as the base paper"],"present","2.2, para 3","Confirm with supervisor"),
 ("L6","Literature (50)","Evaluation and baseline literature (rolling-origin, persistence)","Rubric",["rolling-origin evaluation","persistence"],"present","2.3",""),
 ("L7","Literature (50)","Data and technology limitations (modelled air quality, reanalysis, licences)","Rubric (technology review)",["modelled, not measured","non-commercial"],"present","2.4",""),
 ("L8","Literature (50)","Early-warning practice and responsible AI","Template (secondary objective)",["FATES"],"present","2.5",""),
 ("L9","Literature (50)","Summary of gaps that shape the project","Rubric (links to RQ)",["Summary: gaps that shape the project"],"present","2.6",""),
 ("L10","Literature (50)","Non-peer-reviewed sources flagged","Rubric (quality of referencing)",["is flagged where used"],"present","2, opening paragraph; 2.3 para 2",""),
 # ---- methods ----
 ("M1","Methods","Research method justified against alternatives","Methods marking sheet",["Alternatives were considered"],"present","3.1",""),
 ("M2","Methods","Procedures and tools described (Python, libraries) with justification","Examiner feedback (AA/DD samples)",["Implementation will use Python"],"present","3.2.2, last paragraph","Libraries are planned, not yet installed or decided"),
 ("M3","Methods","Data sources, terms and preparation","Methods marking sheet",["Data sources.","Unplanned"],"present","3.2.1; Table 2",""),
 ("M4","Methods","Baselines and models defined (B1, B2, M1-M3)","Methods marking sheet",["seasonal naive (same week one year earlier)"],"present","3.2.2",""),
 ("M5","Methods","Evaluation design (rolling origin, metrics, test, alert metrics)","Examiner feedback (CC sample)",["rolling-origin testing with an expanding window","Holm"],"present","3.2.3",""),
 ("M6","Methods","Requirements for the prototype (functional and non-functional)","Examiner feedback (EE/CC samples)",["Initial functional requirements are"],"present","3.2.4",""),
 ("M7","Methods","Report on preliminary work already done (report, not proposal)","Template; Methods sheet",["Preliminary work has built the dataset"],"present","3.3, para 1",""),
 ("M8","Methods","Preliminary results shown (data quality, baselines)","Methods sheet",["Data quality checks","Baseline errors on 146 test weeks"],"present","3.3; Tables 3 and 4","No ML model trained yet; baselines only"),
 ("M9","Methods","Development process / lifecycle stated","Examiner feedback (EE sample)",["Development is incremental and prototype-driven"],"present","3.4, para 1",""),
 ("M10","Methods","Schedule tied to module deadlines","Examiner feedback (EE sample)",["Project plan.","27 Nov 2026","9 Apr 2027"],"present","3.4; Table 5",""),
 ("M11","Methods","Risk management","Examiner feedback (EE sample)",["Main risks."],"present","3.4; Table 6",""),
 ("M12","Methods","Ethical, legal and professional issues","Methods marking sheet",["Ethical, legal and professional considerations"],"present","3.5","Ethics-screening route not yet confirmed with supervisor"),
 ("M13","Methods","Diagram of the process (a past marker asked for one)","Examiner feedback (DD sample)",["Planned pipeline from open data"],"present","3.2.4; Figure 1","Pipeline diagram; no separate lifecycle diagram"),
 # ---- references and admin ----
 ("R1","References","References section, author-year style","Template",["References"],"present","End of report",""),
 ("R2","References","No unresolved citations or cross-references in the built PDF","Build check",["??"],"absent_raw","Whole document","Only meaningful for a real LaTeX build"),
 ("A1","Admin","Body within the 4000-word limit","Pro forma / template","", "words","Source count (below)","Also check Overleaf / texcount"),
 ("A2","Admin","Submitted by 6 Nov 2026, 3pm","Deadline photo","", "manual","Submission","Manual"),
 ("A3","Admin","University rules on AI-assisted writing and originality checked","Declaration","", "manual","Declaration","Manual: student must check"),
]

NUMBER_CHECKS = [  # (what, regex in data_quality.md, substring in main.tex)
 ("weeks", r"Weeks: \*\*609\*\*", "609 weeks"),
 ("QEUH mean", r"\| QEUH \| 1812 ", "QEUH 1812"),
 ("GRI mean", r"\| GRI \| 1650 ", "GRI 1650"),
 ("RHC mean", r"\| RHC \| 1251 ", "RHC 1251"),
 ("hottest day", r"Hottest day: \*\*28\.1 C\*\*", "28.1"),
 ("days >=25C", r"Tmax >= 25 C: \*\*24\*\*", "24 days at or above 25"),
 ("days >=27C", r"Tmax >= 27 C: \*\*5\*\*", "5 at or above 27"),
 ("days >=30C", r"Tmax >= 30 C: \*\*0\*\*", "none at 30"),
 ("QEUH baselines", r"\| QEUH \| 146 \| 85 \| 4\.4% \| 71 \| 3\.6% \|", "QEUH & 85 & 4.4\\% & 71 & 3.6\\%"),
 ("GRI baselines", r"\| GRI \| 146 \| 80 \| 5\.0% \| 68 \| 4\.3% \|", "GRI & 80 & 5.0\\% & 68 & 4.3\\%"),
 ("RHC baselines", r"\| RHC \| 146 \| 106 \| 7\.3% \| 97 \| 6\.8% \|", "RHC & 106 & 7.3\\% & 97 & 6.8\\%"),
 ("corr QEUH", r"\| QEUH \| \+0\.34 ", "+0.34 (QEUH)"),
 ("corr GRI", r"\| GRI \| \+0\.25 ", "+0.25 (GRI)"),
 ("corr RHC", r"\| RHC \| -0\.04 ", "$-0.04$ (RHC)"),
]

def condense(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()

def tex_checks():
    tex, bib = read(TEX), read(BIB)
    out = []
    keys = set(re.findall(r"@\w+\{([^,\s]+),", bib))
    cited = set()
    for m in re.finditer(r"\\(?:parencite|textcite|autocite|cite)\{([^}]*)\}", tex):
        cited.update(k.strip() for k in m.group(1).split(","))
    out.append(("Bibliography entries / distinct cited", f"{len(keys)} / {len(cited)}", True))
    out.append(("Cited but missing from .bib", ", ".join(sorted(cited - keys)) or "none", not (cited - keys)))
    out.append(("In .bib but never cited", ", ".join(sorted(keys - cited)) or "none", not (keys - cited)))
    dois = len(re.findall(r"\n\s*doi\s*=", bib))
    out.append(("Entries with a DOI", f"{dois} of {len(keys)} (rest are datasets/web pages/books)", True))
    stack, bad = [], []
    for k, e in re.findall(r"\\(begin|end)\{(\w+\*?)\}", tex):
        if k == "begin": stack.append(e)
        elif stack and stack[-1] == e: stack.pop()
        else: bad.append(e)
    out.append(("LaTeX environments balanced", "yes" if not bad and not stack else f"NO: {bad} {stack}", not bad and not stack))
    body = re.sub(r"(?<!\\)%.*", "", tex)
    depth = 0; ok = True
    for ch in re.sub(r"\\[{}]", "", body):
        depth += (ch == "{") - (ch == "}")
        if depth < 0: ok = False
    out.append(("Braces balanced", "yes" if ok and depth == 0 else "NO", ok and depth == 0))
    labels = set(re.findall(r"\\label\{([^}]*)\}", tex)); refs = set(re.findall(r"\\ref\{([^}]*)\}", tex))
    out.append(("Undefined cross-references", ", ".join(sorted(refs - labels)) or "none", not (refs - labels)))
    # word counts
    s = tex.index("\\section{Introduction}"); e = tex.index("\\addcontentsline{toc}{section}{References}")
    t = re.sub(r"(?<!\\)%.*", "", tex[s:e])
    t = re.sub(r"\\begin\{(table|figure)\}.*?\\end\{\1\}", "", t, flags=re.S)
    def count(txt, cite_words):
        txt = re.sub(r"\\(?:parencite|textcite|cite|autocite)\{[^}]*\}", " CITE " * cite_words, txt)
        txt = re.sub(r"\\ref\{[^}]*\}", " 1 ", txt); txt = re.sub(r"\\label\{[^}]*\}", "", txt)
        txt = re.sub(r"\\(?:section|subsection|subsubsection)\{([^}]*)\}", r" \1 ", txt)
        txt = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", txt); txt = re.sub(r"[{}$\\~]", " ", txt)
        return len([w for w in txt.split() if re.search(r"[A-Za-z0-9]", w)])
    w0, w3 = count(t, 0), count(t, 3)
    out.append(("Body words, citations NOT counted", str(w0), w0 <= LIMIT))
    out.append(("Body words, each citation counted as 3 (conservative)", f"{w3} (limit {LIMIT})", w3 <= LIMIT))
    todo = [p for p in ["[Supervisor name]", "[Second marker name]"] if p in tex]
    out.append(("Placeholders still in main.tex", ", ".join(todo) or "none", not todo))
    return out, (w0, w3)

def number_checks():
    if not os.path.exists(QUAL): return [("data_quality.md found", "NO", False)]
    md, tex = read(QUAL), read(TEX)
    res = []
    for what, rx, sub in NUMBER_CHECKS:
        a = re.search(rx, md) is not None; b = sub in tex
        res.append((what, "matches" if a and b else f"MISMATCH (analysis:{a}, report:{b})", a and b))
    return res

def header_condensed():
    """Running header printed on every page ( \\lhead + \\rhead author ), condensed, so it can be removed before searching."""
    tex = read(TEX)
    lh = re.search(r"\\lhead\{(.*?)\}", tex); au = re.search(r"\\author\{(.*?)\}", tex)
    txt = (lh.group(1) if lh else "").replace("\\&", "&")
    return condense(txt), condense(au.group(1) if au else "")

def pdf_pages(pdf):
    try:
        n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
        pages = []
        for p in range(1, n + 1):
            r = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), pdf, "-"], capture_output=True, text=True)
            c = condense(r.stdout)
            for h in header_condensed():
                if h: c = c.replace(h, "")
            c = re.sub(r"\d{1,3}$", "", c)            # trailing page number
            pages.append((c, r.stdout.lower()))
        return pages
    except Exception:
        return None

def body_start(pages):
    key = condense("Emergency departments (EDs) provide unscheduled care")
    for i, (c, _) in enumerate(pages):
        if key in c: return i
    return 0

def locate(pages, c, lo=0):
    """Page numbers (1-based) where phrase c STARTS, searching the whole document so phrases that wrap
    across a page break are still found."""
    joined = "".join(p for p, _ in pages)
    offs, o = [], 0
    for p, _ in pages: offs.append(o); o += len(p)
    out, i = [], joined.find(c)
    while i >= 0:
        k = max(j for j, off in enumerate(offs) if off <= i)
        if k >= lo: out.append(k + 1)
        i = joined.find(c, i + 1)
    return out

def evaluate(pages):
    rows = []
    start = body_start(pages) if pages else 0
    for rid, area, req, src, phrases, kind, where, note in REQS:
        status, pg = "MANUAL", "n/a"
        if kind == "manual": status = "MANUAL"
        elif kind == "words":
            status = "SEE SOURCE CHECK"
        elif pages is None:
            status = "NO PDF"
        else:
            cs = [condense(x) for x in phrases]
            lo = 0 if area == "Front" else start          # body requirements ignore title/contents/list pages
            if kind == "page2":
                hits = locate(pages, cs[0], 0)
                status = "MET" if hits and min(hits) == 2 else "FAIL"
                pg = ", ".join(map(str, sorted(set(hits))[:3])) or "-"
            elif kind == "absent_raw":
                hits = [i + 1 for ph in phrases for i, (_, raw) in enumerate(pages) if ph.lower() in raw]
                status = "MET" if not hits else "FAIL"
                pg = "-" if not hits else ", ".join(map(str, sorted(set(hits))))
            elif kind == "present":
                found = {c: locate(pages, c, lo) for c in cs}
                allok = all(found[c] for c in cs)
                status = "MET" if allok else "NOT FOUND"
                firsts = sorted({found[c][0] for c in cs if found[c]})
                pg = ", ".join(map(str, firsts)) if firsts else "-"
            elif kind == "absent":
                hits = [pg_ for c in cs for pg_ in locate(pages, c, 0)]
                status = "MET" if not hits else "FAIL"
                pg = "-" if not hits else ", ".join(map(str, sorted(set(hits))))
            elif kind.startswith("count>="):
                need = int(kind.split(">=")[1]); c = cs[0]
                hits = locate(pages, c, lo)
                status = "MET" if len(hits) >= need else "NOT FOUND"
                pg = ", ".join(map(str, sorted(set(hits)))) or "-"
        if note and status == "MET" and any(w in note for w in ("CONFIRM", "TO DO", "Confirm", "confirm")):
            status = "MET (check note)"
        rows.append((rid, area, req, src, where, pg, status, note))
    return rows

def main():
    args = [a for a in sys.argv[1:]]
    rubric = None
    if "--rubric" in args:
        i = args.index("--rubric"); rubric = args[i + 1]; del args[i:i + 2]
    pdf = args[0] if args else None
    pages = pdf_pages(pdf) if pdf and os.path.exists(pdf) else None
    print("== SOURCE CHECKS (main.tex / references.bib) ==")
    tc, (w0, w3) = tex_checks()
    for a, b, ok in tc: print(f"  [{'OK ' if ok else 'FIX'}] {a}: {b}")
    print("\n== NUMBERS vs ../analysis/data_quality.md ==")
    nc = number_checks()
    for a, b, ok in nc: print(f"  [{'OK ' if ok else 'FIX'}] {a}: {b}")
    rows = evaluate(pages)
    print("\n== REQUIREMENTS ==" + ("" if pages else "  (no PDF given: pass a built PDF for page numbers)"))
    print(f"  {'ID':4} {'Status':16} {'Page(s)':10} Requirement")
    for r in rows: print(f"  {r[0]:4} {r[6]:16} {r[5]:10} {r[2][:80]}")
    bad = [r for r in rows if r[6] in ("NOT FOUND", "FAIL")]
    print(f"\nSummary: {len(bad)} requirement(s) not found/failed; "
          f"{sum(1 for a,b,ok in tc+nc if not ok)} source/number check(s) to fix.")
    if rubric:
        L = ["# Rubric cross-check for the interim report", "",
             "Generated by `check_report.py`. **Page numbers refer to the PDF you passed in** "
             f"({os.path.basename(pdf) if pdf else 'none'}). Re-run after your LaTeX build for the real page numbers:",
             "`python3 check_report.py main.pdf --rubric RUBRIC_CHECK.md`", "",
             "Status key: MET = every required phrase found on the page(s) shown; MET (check note) = found but see the note; "
             "NOT FOUND / FAIL = fix; MANUAL = you must check it yourself.", "",
             "Requirement sources: marking-scheme photo (Introduction 25, Literature and technology review 50; the Methods page of that scheme "
             "was not in the photo, so Methods criteria come from the older marking sheets), module template, Word pro forma, examiner feedback "
             "on the six sample reports, and the deadline photo.", "",
             "## Requirements", "", "| ID | Area | Requirement | Source | Where in the report | Page(s) | Status | Note |", "|---|---|---|---|---|---|---|---|"]
        for r in rows: L.append("| " + " | ".join(str(x).replace("|", "/") for x in (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7])) + " |")
        L += ["", "## Source and number checks", "", "| Check | Result | OK |", "|---|---|---|"]
        for a, b, ok in tc + nc: L.append(f"| {a} | {b} | {'yes' if ok else '**FIX**'} |")
        L += ["", "## How to cross-check by hand", "",
              "1. Open the PDF at the page shown for each row and read the paragraph named in 'Where'.",
              "2. For every in-text citation, look it up in `sources_verification.md` (link, grade, what was checked).",
              "3. For every number in Section 3.3, compare it with `../analysis/data_quality.md` (the script does this automatically above).",
              "4. Read the full text of the base paper and the other load-bearing sources before submitting."]
        with open(os.path.join(HERE, rubric), "w", encoding="utf-8") as f: f.write("\n".join(L) + "\n")
        print(f"\nWrote {rubric}")

if __name__ == "__main__":
    main()
