# Project guide for Claude Code

Honours project MHW225671: forecasting weekly A&E attendance in Glasgow from weather, plus a human-approved early-warning
prototype. Read `docs/HANDOVER.md` first, then `docs/ARCHITECTURE.md`.

## Set up and run (do this when asked to "set up the project")
1. Check the machine: Linux or macOS, `python3`, `make`. Windows is not supported. Say so if something is missing.
2. `make setup` (creates `analysis/.venv`, installs `analysis/requirements.txt`; needs internet, about 3 minutes).
3. `make guide` and report the checklist. Do not create officer accounts: `make adduser NAME="..."` asks the human for a
   password, so tell the human to run it themselves (in Claude Code: type `! make adduser NAME="Their Name"`).
4. `make test`. Expected: `18 passed`, `112 / 112 numbers confirmed`, `97 passed`. Show the real output. If it differs, say so.
5. `make demo` starts the offline web page at http://localhost:8000. Tell the human to sign in and press "Take the tour".
   `make` on its own lists every command. Step-by-step guide with troubleshooting: `docs/GETTING_STARTED.md`.

## Rules
- Never claim something works without running it and showing the result.
- Do not commit, push, delete, or overwrite files without the user's explicit approval for that action.
- The repository must stay free of private material. `archive/`, `docs/admin/`, `prototype/accounts/`, `prototype/output/`
  and `prototype/data/` are git-ignored on purpose. Never add them, and never print or commit passwords or `users.json`.
- The report carries the student's name and ID. Do not publish it anywhere public.
- Numbers in documents come from `analysis/results/`; `make test` checks the ones in `analysis/RESULTS.md`. Do not run
  `make reproduce` unless asked: it rewrites the results.
- Report text submitted by the student must be the student's own words. The university's AI-writing policy has not been
  checked yet. Do not draft report text for submission until the user confirms what the policy allows.
- This is decision support, not clinical advice. Do not describe it as validated or endorsed by Public Health Scotland or the NHS.

## Layout
`analysis/` the study (start with `RESULTS.md`), `prototype/` the tool, `report/` interim report and final-report draft,
`docs/` guides and status, `Makefile` short commands.
