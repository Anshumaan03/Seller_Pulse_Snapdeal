# Implementation notes

Short record of the choices made while building, plus the checklist I worked against.

## Choices

- **Workspace was empty**, so no existing project or sample seller file was reused. The demo dataset is synthetic and labelled that way everywhere (file, API, UI, docs).
- **Backend:** Python + FastAPI + Pydantic + SQLite. Business maths lives in plain functions (`analytics.py`).
- **Frontend:** plain HTML/CSS/JS served by FastAPI. The brief suggested React + Vite; I skipped it because there is no build step to break on demo day and the page is one screen. Easy to port later.
- **Voice:** browser speech recognition + speech synthesis (no API key). The provider sits behind the browser, and the server only ever sees text, so a realtime voice API can replace it without touching the tools or the dialogue controller.
- **Agent:** a stateful dialogue controller that calls typed tools. An LLM is optional and limited to rewording and labelling unclear answers, behind guards. In the default run no LLM is called.
- **Consent:** `create_action_plan` raises unless the caller passes `consent_confirmed=True`, and the controller only does that after the seller says yes to a read-back draft.

## Checklist

- [x] Inspect workspace (empty) and environment (no API keys present)
- [x] Synthetic dataset that reconciles (orders x AOV = GMV; SKU orders sum to account orders)
- [x] 8 tools with typed inputs/outputs
- [x] Multi-turn dialogue: concern -> diagnosis -> questions -> draft plan -> consent -> saved plan -> recap
- [x] Two or more branches (restock soon / none / unknown; price: strict / manual / open / no room / unknown)
- [x] Voice UI: Start, End, Mute mic, Mute speaker, Speak/interrupt, Try demo seller, Reset
- [x] Plan persisted in SQLite and cleared by Reset
- [x] Automated tests (56) and a headless UI check
- [x] Clean-start run from README in a fresh copy
- [ ] Real microphone + speaker test in Chrome (needs a person; see docs/testing-checklist.md)
- [ ] Live LLM provider check (needs a key; `python backend/check_llm.py`)
- [ ] Screen recording (must be recorded by the applicant)
