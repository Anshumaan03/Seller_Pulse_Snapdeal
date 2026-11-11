# Architecture

## The short version

The browser handles audio. The server handles everything else. The server only ever sees text.

```
 Seller speaks
     |
     v
 Chrome SpeechRecognition (en-IN)              <- browser, needs internet (Google's speech service)
     |  text
     v
 POST /api/call/{id}/message  -------------------------------+
     |                                                       |
     v                                                       |
 agent.py  dialogue controller                               |
   1. nlu.py        pull out intent + slots (days, Rs, policy)
   2. tools.py      call a tool for every number it will say
        |-- analytics.py   % change, AOV, conversion, SKU gaps, driver ranking
        |-- planner.py     drivers + seller answers -> draft actions
        |-- db.py (SQLite) plans, call summaries
   3. pick the next question that could change the plan, or present the draft
   4. (optional) llm.py    reword the reply; rejected if any number/name changes
     |  reply text                                           |
     v                                                       |
 JSON response  <--------------------------------------------+
     |
     v
 Browser SpeechSynthesis speaks it, UI shows transcript + plan
```

## Voice flow

1. Click **Start call** (this click is what lets the browser play audio and ask for the mic).
2. The server returns the greeting. The browser speaks it sentence by sentence.
3. When speech ends, recognition starts. States shown: Connecting, Listening, Thinking, Speaking, Call ended.
4. A final transcript goes to the server. The mic is stopped while the agent talks so it does not hear itself.
5. **Speak / interrupt** (or Space) cuts the agent off and starts listening again.

Errors (mic denied, no mic, network, empty transcript) turn into readable messages in the call panel.

## Agent orchestration

`agent.py` is a small state machine: `concern -> ask -> consent -> after_plan -> ended`.

- **Slots, not a script.** Every seller utterance is scanned for facts (restock days, minimum price, price policy, dispatch cause). If the seller volunteers two answers at once, both are taken and neither question is asked.
- **Questions are computed, not scheduled.** `_pending_question` looks at the drivers and at what is already known and asks only what would change the plan. Today that is restock timing and the margin floor.
- **Consent is a stage.** The plan is read aloud and shown as "Proposed". Only a yes moves it to saved. A "no", a change request ("skip the jar one"), or a price-policy correction re-opens the draft.

## Deterministic tools

Typed with Pydantic in `models.py`. The LLM (when on) never calls them; the controller does.

| Tool | What it returns |
|---|---|
| `get_seller_profile` | seller, category, windows, data label |
| `get_period_comparison` | GMV, orders, sessions, AOV, conversion, % changes, and an arithmetic split of lost orders into traffic vs conversion |
| `get_sku_diagnostics` | per-SKU order change, stockout, price gap, return/dispatch/cancellation gaps (None when the data has nothing) |
| `identify_sales_drivers` | ranked drivers: observed facts, a hypothesis worded as one, what to verify, missing data, impact/confidence/urgency |
| `estimate_action_priority` | score = impact x3 + urgency x2 + confidence x2 - effort, plus a blocked reason (e.g. margin floor unknown). No revenue uplift is ever estimated |
| `create_action_plan` | saves draft items; raises without consent |
| `get_action_plan` | reads the saved plan back |
| `log_call_summary` | stores a short summary, decisions, follow-up |

## Data and action-plan flow

`data/demo_seller.json` (synthetic) -> `analytics.py` -> drivers -> `planner.py` builds draft `ActionItem`s from drivers + the seller's answers -> shown as "Proposed" -> seller says yes -> `create_action_plan(consent_confirmed=True)` -> SQLite -> "Saved plan" in the UI. Every saved item carries `simulated=true` and the status "Draft (simulated)".

## Optional LLM layer

Off unless `LLM_API_KEY` and `LLM_MODEL` are set. Two jobs only:

- `rewrite(draft)`: reword the controller's reply. `guard_ok` rejects it if any number differs, a new product-like name appears, the question is dropped, it claims a change was made, or it gets much longer. On rejection or any error the original text is used.
- `classify(text)`: label an unclear answer as yes / no / dont_know / not_now / repeat / other.

## Why the server never sees audio

Keeping audio in the browser means no audio is uploaded to this server and no speech key is needed. The cost is that Chrome's recognizer sends audio to Google, and there is a pause between turns. Swapping to a realtime speech-to-speech API would replace the browser audio layer; the tools, data and consent logic stay as they are.
