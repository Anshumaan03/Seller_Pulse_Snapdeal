# Handoff: how to own, record and submit this

## 1. What was built, in plain language

You call SellerPulse. It says it is a prototype on sample data, then asks what you have noticed. You say your orders are down. It already has the numbers: orders down 30%, visits down 10%, conversion slipping. It tells you the biggest finding (a top product was out of stock for 9 days) and asks if fresh stock is coming. Your answer changes the plan. It asks about your minimum price before touching pricing. Then it reads a draft plan back, asks "shall I save this?", and only on your yes saves it, marked as a simulated draft. It ends with a recap.

## 2. Architecture you can repeat from memory

Browser mic -> Chrome speech recognition -> text to the server -> dialogue controller (`agent.py`) -> tools (`tools.py` -> `analytics.py`) -> reply text -> browser speech synthesis -> speaker. Plan and summary go to SQLite. Diagram in `docs/architecture.md`.

Three sentences to say it: *"The browser does the audio, the server only sees text. A small state machine decides what to say and calls typed tools for every number. Nothing is saved until the seller says yes."*

## 3. File map: read in this order (about 45 minutes)

1. `data/demo_seller.json`: the fake seller. Check that the numbers reconcile.
2. `backend/app/analytics.py`: the maths and the driver ranking. Most important file to understand.
3. `backend/app/tools.py`: the 8 tools and the consent guard in `create_action_plan`.
4. `backend/app/planner.py`: how the seller's answers change the draft plan.
5. `backend/app/agent.py`: the conversation. Read `_route`, `_advance`, `_fill_slots`, `_save_plan`.
6. `backend/app/nlu.py`: keyword rules. Skim.
7. `frontend/app.js`: the voice loop (`listen`, `speak`, `sendText`).
8. `backend/tests/test_conversation.py`: shows every behaviour as an example. Good for learning what the agent does.

## 4. Commands (run from the repo root, the folder with README.md)

**Windows PowerShell**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
python -m uvicorn backend.app.main:app --port 8000
```
**macOS / Linux**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
uvicorn backend.app.main:app --port 8000
```
Open **http://localhost:8000** in Chrome. Stop the server with Ctrl+C.

## 5. Making it yours (do this before you record)

Reading is not enough. The discussion round is where you explain it, so change something yourself and watch the tests react:

- Change a threshold, for example the price-gap flag (`> 3` in `identify_drivers`) or the priority weights. Run the tests; see which fail and why.
- Add a third question, such as "what is behind the dispatch delays?" Hint: `_pending_question` and `_question_text` in `agent.py`, the slot already exists in `nlu.extract_dispatch_cause`.
- Reword the greeting or the closing in your own voice.
- Edit the "What I built and why" section in `docs/design-decisions.md` until every sentence is something you would say.
- Put it in git under your name with your own commit messages: `git init && git add . && git commit -m "SellerPulse: Virtual KAM prototype"`. Check `git status` does not list `.env` or `data/*.db`.

Quick self-test. Explain, without looking: why the numbers are not produced by a model; what stops a plan being saved without consent; what the traffic/conversion split means and does not mean; why the price gap is "a lead, not proof"; what is real and what is mocked.

## 6. Optional: turn on an LLM (about 5 minutes)

Not needed. It only rewords replies and labels unclear answers. If you want an LLM in the stack for the discussion:

1. Get a key from Google AI Studio (https://aistudio.google.com/app/apikey), or use any OpenAI-compatible provider.
2. Copy `.env.example` to `.env`. Fill `LLM_API_KEY` and `LLM_MODEL` (use a current model ID from the provider's docs; model names change). Do not paste the key anywhere else, and never into chat.
3. Run `python backend/check_llm.py`. It prints a test rewrite and says whether the guard accepted it. It does not print your key.
4. Restart the server. **Under the hood** tab shows `llm.enabled: true`.
5. Do a full call and re-check the numbers. If anything sounds off, remove the key; the app falls back to rule-based wording.
6. Fill the model name into `docs/model-and-voice-note.md`.

I could not test a live provider in the build environment, so treat step 3 as the real test.

## 7. Running the demo

- Chrome (or Edge), on `http://localhost:8000`. Chrome allows the mic on localhost; it will not on a plain IP address.
- Internet on (Chrome's speech recognition uses Google's service).
- Select **DEMO-1042** (already selected). **Try demo seller** just reloads it. Click **Reset demo**.
- Click **Start call**, allow the mic. After the greeting, say: **"My orders have gone down quite a bit. I'm not sure what's wrong."**
- Full lines and the on-screen moments are in `docs/demo-script.md`.

## 8. Recording the 1-2 minute video: file name `SellerPulse_Demo.mp4`

**Setup (2 minutes)**
- Close other tabs and apps; turn off notifications. Browser window about 1280 px wide, 100% zoom.
- Pick a recorder that captures **your microphone**: OBS Studio (free), Loom, or the built-in recorder (Windows Game Bar `Win+G`; macOS `Cmd+Shift+5` with a microphone selected).
- The simplest reliable audio: use **speakers (not headphones) at moderate volume** and record with your mic on. Your mic then captures both your voice and the agent's voice. The app pauses its own listening while it talks, so it will not answer itself. Make sure the room is quiet.
- If you want cleaner audio, use OBS with "Desktop Audio" plus your mic, and wear headphones.
- **Audio check:** record 10 seconds, say a sentence, let the agent greet, stop, and play it back. Both voices must be clearly audible.
- Click **Reset demo**. Run one rehearsal call first so Chrome's mic permission is already granted.

**Shot list (target 90-110 seconds)**
| Time | Shot |
|---|---|
| 0:00-0:05 | Full app on screen. Pause so the "Synthetic demo data" badge and snapshot are visible. Optional one line to camera/voice: "This is SellerPulse, my Virtual KAM prototype." |
| 0:05-0:25 | Click Start call. Agent greeting plays. State label shows Speaking then Listening. |
| 0:25-0:50 | You say the first line. Agent gives the data-backed finding and asks about stock. Right panel shows the observed vs hypothesis signals. |
| 0:50-1:15 | You answer about restock. Agent gives the other signals and asks for your minimum price. |
| 1:15-1:40 | You answer about margin. Agent reads the draft plan. Action plan tab shows "Proposed". |
| 1:40-1:55 | You say yes. Agent confirms it is saved in the demo. Plan switches to "Saved plan", status "Draft (simulated)". Linger two seconds. |
| End | Stop recording. Optionally say "No, that's all" first for the recap. |

Watch the video once end to end with sound. Re-record if the agent mis-hears; it happens.

## 9. Submitting

1. Upload the video (Google Drive set to "anyone with the link can view", or YouTube unlisted). Open the link in a private window to confirm.
2. Share the code: a GitHub repo (check no `.env` and no key inside; make it public or add Sourav) or a zip of this folder without `.venv` and `data/*.db`.
3. Attach or link `docs/model-and-voice-note.md`.
4. Fill `docs/submission-email.md`. Replace every bracket. Do not write a live URL you have not made. This project runs locally; say you are happy to do a live demo.
5. Check the real deadline in Sourav's email thread. It mentions both 24 and 48 hours, so confirm from the timestamp or ask him directly.

## 10. If shortlisted: the live demo

- Have the server running, Chrome open, headphones on, `Reset demo` clicked. Test the mic five minutes before.
- Open with the 3-sentence architecture, then run the call. Keep your own wording.
- Have `analytics.py`, `tools.py` and `agent.py` open in an editor in case he wants to see code.
- If voice recognition fails live, say so and use the typed box. That fallback exists for this.
- Questions and answers to rehearse: `docs/technical-discussion-prep.md`.

## 11. What is real, mocked and untested

- **Real:** the browser voice interaction, all calculations, the dialogue logic, the consent rule, SQLite persistence, the 56 automated tests and the headless UI check.
- **Mocked:** all seller data, the "benchmark" and "targets", and every action (simulated drafts). No Snapdeal system is touched.
- **Not tested by me:** a real microphone and speakers in Chrome, a live LLM provider, other browsers.
- **Next improvement:** a realtime speech-to-speech layer with real interruption, Hindi support, and an LLM tool-calling loop on top of the same tools.
