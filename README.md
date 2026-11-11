# SellerPulse: Virtual KAM prototype

**From a sales dip to the next best action.**

A voice-first prototype of a Virtual Key Account Manager for online marketplace sellers. A seller talks to it about a sales drop; it looks at the seller's numbers, explains the likely reasons, asks the one or two questions that change the advice, and ends with an action plan the seller approves.

Built for the Snapdeal AI First Intern assessment. It is an independent prototype. It is not an official Snapdeal product and has no access to any Snapdeal system.

> **All data is synthetic.** The seller (Riya Home & Living), the SKUs, the "benchmark price" and the "targets" in `data/demo_seller.json` are fabricated for this demo. They are not Snapdeal data, market data or Snapdeal standards. Every action the agent creates is a simulated draft. Nothing is applied to any real account.

## What it does

1. **Listen** - the seller speaks into the browser; the agent answers out loud.
2. **Understand** - it remembers what the seller said (restock date, minimum price, price policy) and does not ask the same thing twice.
3. **Diagnose** - Python functions compare the last 30 days with the 30 before and split the drop into traffic, conversion and per-product signals.
4. **Decide** - actions are ranked by impact, urgency, confidence and effort, with the evidence shown.
5. **Drive action** - the agent reads a draft plan aloud and asks for a yes. Only then is it saved, marked as a simulated draft.

## Architecture in one paragraph

Browser mic -> Chrome speech recognition -> text -> `POST /api/call/{id}/message` -> dialogue controller (`agent.py`) -> backend tools (`tools.py` -> `analytics.py`) -> reply text -> browser speech synthesis -> speaker. Plans and call summaries go to SQLite. An optional LLM can reword replies and label unclear answers, but it cannot change a number or skip the consent step. Details: [docs/architecture.md](docs/architecture.md).

## Requirements

- Python 3.10 or newer (tested on 3.13)
- Google Chrome (or Edge) with a working microphone and speakers/headphones
- Open the app on **http://localhost:8000**. Chrome only allows the microphone on `localhost` or HTTPS.
- Internet connection: Chrome's speech recognition sends audio to Google's service to transcribe it.
- No API key is needed for the default mode.

## Setup and run

Run everything from the repository root (the folder that contains `README.md`).

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --port 8000
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --port 8000
```

If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process Bypass` first.

Then open http://localhost:8000 in Chrome. `make setup` and `make run` do the same on macOS/Linux.

## Try it

1. Click **Start call** and allow the microphone.
2. Wait for the greeting, then say: *"My orders have gone down quite a bit. I'm not sure what's wrong."*
3. Answer the questions in your own words. The full suggested path is in [docs/demo-script.md](docs/demo-script.md).
4. Watch the **Action plan** tab. It shows "Proposed" first, and "Saved plan" only after you say yes.
5. **Reset demo** clears the plan and the call so you can run it again.

Use headphones if you can. In this browser voice mode the mic is paused while the agent speaks (so it does not hear itself). Press **Space** or **Speak / interrupt** to cut the agent off and talk.

## Environment variables (all optional)

Copy `.env.example` to `.env` to use any of these. The file is git-ignored; keys are read by the server only and are never sent to the browser.

| Variable | Purpose |
|---|---|
| `LLM_API_KEY`, `LLM_MODEL` | Turns on the optional LLM layer. Both must be set. Use a current model ID from your provider's docs. |
| `LLM_BASE_URL` | OpenAI-compatible endpoint. Defaults to Google's Gemini endpoint. |
| `SELLERPULSE_DB` | SQLite file for plans and summaries (default `data/sellerpulse.db`). |
| `SELLERPULSE_DATA` | Path to a different seller JSON file with the same shape. |

Check that no key is exposed: `git grep -n "API_KEY"` should only show `.env.example` and the code that *reads* the variable, and `.env` must not be tracked (`git status` should never list it).

## Tests

```bash
python -m pytest -q                              # unit + API + conversation tests (no browser, no key)
python backend/tests/ui_smoke.py                 # optional: headless Chrome check, needs `pip install playwright` and the server running
```

The UI smoke test replaces the microphone and speaker with fakes, so it checks the page logic, not real audio. The manual voice checklist is in [docs/testing-checklist.md](docs/testing-checklist.md).

## Project layout

```
backend/app/analytics.py   deterministic maths: % change, AOV, conversion, SKU signals, driver ranking
backend/app/tools.py       the 8 agent tools (typed in models.py), plus the consent guard
backend/app/planner.py     turns drivers + seller answers into draft actions
backend/app/agent.py       dialogue controller: state, slots, questions, consent, closing
backend/app/nlu.py         small keyword/regex language understanding (English + some Hinglish)
backend/app/llm.py         optional LLM layer with guards (off by default)
backend/app/prompts.py     system prompt for that layer
backend/app/main.py        FastAPI endpoints + serves the frontend
backend/app/db.py          SQLite for plans and call summaries
frontend/                  plain HTML/CSS/JS, no build step
data/demo_seller.json      synthetic demo data
docs/                      architecture, design decisions, demo script, tests, interview prep, email draft
```

## Troubleshooting

| Problem | What to do |
|---|---|
| "Microphone access is blocked" | Click the lock icon next to the address bar, allow the microphone, press Start call again. |
| No voice recognition at all | Use Chrome or Edge, and open `http://localhost:8000` (not an IP address or file). Firefox does not support this speech API. |
| "Speech service could not be reached" | Chrome's recognition needs internet. Check your connection or VPN. |
| Agent is silent | Check the speaker is not muted in the app or the OS. Some systems have no English voice installed; install one in system settings. |
| It keeps hearing itself | Use headphones. |
| `pip` or `uvicorn` not found | Activate the virtual environment first. |
| Port 8000 busy | Use `--port 8001` and open that port instead. |
| Want a clean slate | Click **Reset demo**, or delete `data/sellerpulse.db`. |

## Known limits

- Voice is Chrome's built-in speech recognition and the browser's speech synthesis, not a streaming speech-to-speech model, so there is a pause after each sentence and no automatic barge-in.
- Replies are in English. A few common Hinglish words are understood, but the agent does not speak Hindi.
- The dialogue is rule-based by default. It handles the scenarios in the tests; very free-form speech may get a "didn't catch that".
- One demo seller, one pair of time windows, no real Snapdeal data or APIs.

More in [docs/design-decisions.md](docs/design-decisions.md).
