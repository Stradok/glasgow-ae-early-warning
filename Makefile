# Short commands for the whole project. Run `make` to see them. Needs Python 3 (developed and tested on 3.14.4; other versions untested) and make.
# Everything uses one virtual environment at analysis/.venv, which is git-ignored.
# Relative paths on purpose: make cannot cope with spaces in absolute paths.
VENV_PY := analysis/.venv/bin/python
# The same interpreter by absolute path, quoted for use in recipes (a ../ path makes Python 3.14 print a warning).
PY := "$(CURDIR)/analysis/.venv/bin/python"

.DEFAULT_GOAL := help
.PHONY: help setup guide guide-demo demo serve adduser refresh test test-analysis test-prototype reproduce report

help:
	@echo "First time:    make setup      create the environment and install packages"
	@echo "               make guide      check what is ready and what to do next (make guide-demo for the offline demo)"
	@echo "Try it:        make adduser NAME=\"Your Name\"   (asks for a password)"
	@echo "               make demo       offline demo web page at http://localhost:8000"
	@echo "Real use:      make refresh    pull the latest data (needs internet)"
	@echo "               make serve      the real web page at http://localhost:8000"
	@echo "Check:         make test       all tests and the number check (about 1 minute)"
	@echo "Rebuild:       make reproduce  re-run every experiment (about 10 minutes, changes results/)"
	@echo "               make report     build report/main.pdf (needs LaTeX)"

setup:
	python3 -m venv analysis/.venv
	analysis/.venv/bin/pip install -r analysis/requirements.txt
	@echo "Done. Next: make guide"

$(VENV_PY):
	@echo "No environment yet: run  make setup  first." >&2; exit 1

# If packages are missing or broken the tool cannot even start, so check that first.
DEPS := import numpy, pandas, scipy, pygam, matplotlib, holidays, statsmodels, sklearn, xgboost
CHECK_DEPS = $(PY) -c "$(DEPS)" 2>/dev/null || { echo "Packages are missing or broken: run  make setup  again." >&2; exit 1; }

guide: $(VENV_PY)
	@$(CHECK_DEPS)
	cd prototype && $(PY) alert_tool.py guide

guide-demo: $(VENV_PY)
	@$(CHECK_DEPS)
	cd prototype && $(PY) alert_tool.py --demo guide

adduser: $(VENV_PY)
	@test -n "$$NAME" || { echo "usage: make adduser NAME=\"Your Name\"" >&2; exit 1; }
	cd prototype && $(PY) alert_tool.py adduser "$$NAME"

demo: $(VENV_PY)
	cd prototype && $(PY) alert_tool.py --demo serve

serve: $(VENV_PY)
	cd prototype && $(PY) alert_tool.py serve

refresh: $(VENV_PY)
	cd prototype && $(PY) alert_tool.py refresh

test-analysis: $(VENV_PY)
	cd analysis && $(PY) -m pytest tests -q && $(PY) -I check_results.py

test-prototype: $(VENV_PY)
	cd prototype && $(PY) -m pytest tests -q

test: test-analysis test-prototype

reproduce: $(VENV_PY)
	cd analysis && $(PY) -I run_experiments.py && $(PY) -I robustness.py && $(PY) -I forecast_weather_test.py \
	  && $(PY) -I alerts_eval.py && $(PY) -I make_figures.py && $(PY) -I make_tables.py && $(PY) -m pytest tests -q && $(PY) -I check_results.py

report:
	cd report && latexmk -pdf -interaction=nonstopmode main.tex
