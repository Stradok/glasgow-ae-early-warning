# Getting started: run the prototype in 10 minutes

This guide takes you from a fresh download to a working web page, then shows how to use it. Do the steps in order.
Each step says what you should see, so you know it worked.

**You need:** Linux or macOS (Windows is not supported), Python 3 (developed and tested on 3.14.4; other versions are
untested), `make`, and internet access for step 1 and for real (non-demo) use only.

## Step 1. Install (about 3 minutes)

```
make setup
```
This creates a private Python environment in `analysis/.venv` and installs the packages listed in
`analysis/requirements.txt`. You should see pip installing packages and then `Done. Next: make guide`.

Without `make`:
```
python3 -m venv analysis/.venv && . analysis/.venv/bin/activate && pip install -r analysis/requirements.txt
```

## Step 2. Ask the tool what is ready

```
make guide
```
A checklist appears, and the line `Next step:` tells you what to do. Run this command whenever you are unsure. It also notices
missing or broken packages. If you only want the offline demo, use `make guide-demo`: it leaves out the live-data step.
On a fresh download the first missing item is "At least one officer account exists".

## Step 3. Create an officer account

```
make adduser NAME="Your Name"
```
It asks for a password twice (10 to 200 characters). The account is stored, with the password salted and hashed, in
`prototype/accounts/users.json`. That file is git-ignored and never leaves your computer. The first account needs no
authorisation. Every later account needs an existing officer's name and password.

## Step 4. Start the offline demo

```
make demo
```
Open http://localhost:8000 and sign in with the name and password from step 3. The demo needs no internet. It pretends a past
week (the week ending 18 October 2026) is the forecast, and it writes to a separate demo log, never to the real one.
Stop it with Ctrl+C.

## Step 5. Take the tour, then try the workflow

A guided tour starts by itself on the first visit. It has 8 steps and explains the summary strip, the hospital cards, the
decision panel and the audit log. Press Esc to skip it. Reopen it any time with **Take the tour** in the top bar.

Then try the full workflow once:
1. Press **Run the demo forecast** (in real mode the button says **Run forecast now**). Three cards appear, one per hospital, each with a risk label (Low, Medium or High), a
   forecast, a 52-week chart and the main drivers.
2. A High forecast creates an alert under **Needs your decision**. The demo uses one fixed week, so it creates one alert (for GRI) and creates it only once: the demo log remembers it. To start the demo over, stop the tool and delete `prototype/output/alert_log_demo.jsonl` (the demo log only; it holds no real decisions). Press **Approve**, or **Reject** (a reason is required).
3. After an approval, press **Release message**. A text file appears in `prototype/output/released_demo/` (in real mode: `prototype/output/released/`).
4. Look at the **audit log** at the bottom. It shows who did what and confirms the log's integrity check.

## Step 6. Use real data (needs internet)

Stop the demo, then:
```
make refresh      # pulls the latest attendance and weather, about a minute
make serve        # the real page: http://localhost:8000
```
Press **Run forecast now**. The forecast is for the week after the last week Public Health Scotland has published. The
tool tells you when that week has already ended, because Public Health Scotland publishes each week's figures about nine days after it ends (per the dataset page).

## Step 7. Check everything works

```
make test
```
This runs the analysis tests, the check that every number in `analysis/RESULTS.md` matches the result files, and the
prototype tests. It takes about a minute. You should see `18 passed`, `112 / 112 numbers confirmed` and `97 passed`.

## Command line instead of the web page

Everything the web page does is also available in a terminal. From the `prototype/` folder with the environment
active:

| Command | What it does |
|---|---|
| `python alert_tool.py guide` | Checklist and next step |
| `python alert_tool.py forecast` | Live forecast, risk and drivers |
| `python alert_tool.py pending` | Alerts waiting for a decision |
| `python alert_tool.py approve <id> --officer "Name"` | Approve (asks for your password) |
| `python alert_tool.py reject <id> --officer "Name" --reason "..."` | Reject |
| `python alert_tool.py release <id> --officer "Name"` | Release an approved alert |
| `python alert_tool.py log` | Full audit trail |

Add `--demo` before the command (for example `python alert_tool.py --demo pending`) to use the demo log.

## When something goes wrong

| What you see | Cause and fix |
|---|---|
| `No environment yet: run make setup first.` | Step 1 has not been done, or the folder was moved. Run `make setup` again. |
| `cannot start the web page on port 8000` | Another program uses that port. The message gives the command with another port (for the demo: `python alert_tool.py --demo serve --port 8001`, run from `prototype/` with the environment active). |
| `Too many wrong attempts for that name` | Five wrong passwords lock that name for 60 seconds. Wait and retry. |
| Forgot a password | There is no reset. Stop the tool and delete `prototype/accounts/users.json`, then create the account again (step 3). Old log entries keep the old name. |
| `log inconsistent` or the integrity check fails | The audit log file was edited or damaged. Decisions are refused on purpose. Keep the file as evidence and ask the project owner before changing it. |
| `cannot forecast: ...` | Usually missing live data. Run `make refresh`, or use `make demo`. |
| `refresh` fails | No internet, or Open-Meteo or Public Health Scotland is down. Retry later; the demo still works. |
| `Packages are missing or broken` or `ModuleNotFoundError` | The environment is incomplete, or you are not using it. Run `make setup` again. Use the `make` commands, or `. analysis/.venv/bin/activate` first. |

## Where to go next

- How it works and why: [ARCHITECTURE.md](ARCHITECTURE.md)
- What the results mean: [../analysis/RESULTS.md](../analysis/RESULTS.md)
- Prototype details and limits: [../prototype/README.md](../prototype/README.md)
