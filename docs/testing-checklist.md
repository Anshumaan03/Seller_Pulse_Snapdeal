# Testing checklist

## Automated (run from the repo root, venv active)

```bash
python -m pytest -q
```

Result when this was built: **56 passed**. It covers: percentage-change/AOV/conversion maths and zero/missing guards; data reconciliation; SKU decline ranking and gaps; driver ranking and "follows the data, not a script"; price/restock branches; consent (no plan saved without yes, tool refuses without consent flag); no repeated questions; repeat / don't know / not now / wrong number / garbled input; item removal at the confirmation; all API endpoints (snapshot, diagnosis, plan create/read, call summary, full call over HTTP, reset); LLM guard and fallback using fakes.

Optional headless-Chrome check of the voice page logic (fake mic and speaker, so it tests the page, not real audio):

```bash
pip install playwright        # once
uvicorn backend.app.main:app --port 8000     # in another terminal
python backend/tests/ui_smoke.py
```

Result when this was built: **PASS**, no console errors. It drove Start call, four spoken turns, proposed then saved plan, end of call, reset, and the "microphone blocked" message.

## Not tested by me - please do these yourself

I had no microphone, speaker or live LLM key in the build environment, so these need a person. Mark each pass/fail.

### Browser and permissions
- [ ] Chrome (current) at `http://localhost:8000`. Page loads, snapshot and signals visible, "Synthetic demo data" badge shown.
- [ ] Nothing asks for the microphone until **Start call** is clicked.
- [ ] Allow the microphone: the call continues. Block it (or reset the permission and deny): readable message, no crash.
- [ ] Unplug/disable the mic: "No microphone was found" message.
- [ ] Open in Firefox: page tells you voice input needs Chrome/Edge; agent still speaks; typed box works.

### Voice
- [ ] Greeting is audible after Start call (no audio before the click).
- [ ] State label cycles Connecting, Speaking, Listening, Thinking, Speaking.
- [ ] Say the suggested first line. Live words appear under the caption; the reply is spoken.
- [ ] Say nothing for ~10 seconds: it retries, then shows "I'm not hearing anything".
- [ ] **Speak / interrupt** (and Space) cuts the agent off and starts listening.
- [ ] **Mute mic** stops it listening; **Unmute mic** resumes.
- [ ] **Mute speaker** silences it; text still appears.
- [ ] Say "repeat that": agent repeats the last reply.
- [ ] Say "I don't know" to a question: it moves on without asking again.
- [ ] Say "not now": call ends politely, no plan saved.
- [ ] Say "that number is wrong": it acknowledges and carries on.

### Plan and consent
- [ ] Plan tab shows **Proposed** before you say yes, and the saved plan is **not** there yet (refresh and check: nothing persisted).
- [ ] Say "no": agent says nothing is saved and asks what to change.
- [ ] Say yes: table switches to **Saved plan** with status "Draft (simulated)".
- [ ] Banner "Simulated drafts only" is visible. Agent never says it changed a price or stock.
- [ ] **Reset demo** clears the plan, transcript and call state; the same scenario runs again.
- [ ] Refresh the page after saving a plan: the saved plan is still shown (it lives in SQLite) until you click Reset demo.

### Optional LLM (only if you set a key)
- [ ] `python backend/check_llm.py` prints a rewritten sentence and a Guard verdict, and does not print your key.
- [ ] A full call still gives the same numbers as without the key.
- [ ] Turn the network off mid-call: replies continue in rule-based wording.

### Secrets
- [ ] `git status` never lists `.env`.
- [ ] `git grep -n "AIza\|sk-"` returns nothing.
- [ ] No key appears in the browser's Network tab or in your recording.
