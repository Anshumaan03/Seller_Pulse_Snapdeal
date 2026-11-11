# SellerPulse: AI models and voice technologies used

## Summary

SellerPulse is a voice-first Virtual KAM prototype. The seller talks, a Python dialogue controller calls deterministic tools for every number, and a plan is saved only after the seller says yes. It runs without any LLM; one can be switched on to reword replies.

| Layer | What the code actually uses | Where |
| --- | --- | --- |
| Speech to text | Browser Web Speech API, SpeechRecognition (webkitSpeechRecognition in Chrome), language en-IN | frontend/app.js |
| Text to speech | Browser speechSynthesis, an en-IN voice when the system has one | frontend/app.js |
| Conversation logic | Rule-based dialogue controller with keyword and regex understanding | backend/app/agent.py, nlu.py |
| Business maths | Plain Python functions over a synthetic JSON dataset | backend/app/analytics.py |
| LLM (optional) | OpenAI-compatible chat-completions call, used only to reword replies and label unclear answers. In the demo: none (rule-based mode) | backend/app/llm.py |
| Server and storage | FastAPI, Pydantic, SQLite | backend/app/main.py, db.py |

## Voice layer

Audio stays in the browser; the server only ever receives text. That needs no speech API key and no audio upload, and it runs wherever Chrome does.

How one call runs:

1. The seller clicks Start call. That click is what lets the browser play audio and ask for the microphone, so nothing is requested before it.
2. The server returns the greeting and the browser speaks it, sentence by sentence. Long single utterances get cut off in some Chrome voices, so replies are queued as short sentences.
3. When speech ends, recognition starts with interim results on, so the seller sees their words appear live.
4. The final transcript is sent to the server. The microphone is stopped while the agent talks so it does not hear itself.
5. The reply comes back, is spoken, and listening starts again. The Speak / interrupt button (or the Space key) cuts the agent off and listens immediately.

Failures turn into readable messages instead of crashes: microphone blocked, no microphone, network error, nothing heard (it retries twice, then asks the seller to check the mic), and an unsupported browser (the agent still speaks and replies can be typed).

I chose browser speech over a realtime speech-to-speech model for three reasons: it needs no paid key, it is reliable enough to demo live, and the audio layer is separate from the logic, so it can be replaced later without touching the tools or the consent rule.

## Conversation engine

The agent is a small state machine in Python, not a free-running LLM. It keeps structured state (facts the seller has told it, the question it is waiting on, the drafted actions, consent) and calls typed tools for every number it says.

| Stage | What happens | Moves on when |
| --- | --- | --- |
| concern | Seller describes the problem. Agent fetches the comparison and drivers and states the main finding | Any usable first answer |
| ask | Agent asks the next question whose answer would change the plan (restock timing, then minimum price) | Every needed answer is known |
| consent | Agent reads the draft plan aloud and asks to save it | Seller says yes (saved), no or a change (re-opened) |
| after_plan | Plan is saved as a simulated draft; recap or follow-up questions | Seller is done |
| ended | Summary logged | Call over |

Three behaviours that make it feel like a conversation and not a form:

- Slots, not a script. Every utterance is scanned for facts (days, rupee amounts, price policy). If the seller gives two answers at once, both are taken and neither question is asked again.
- Computed questions. The next question is recomputed from the data and what is already known, so nothing is asked twice.
- Consent is a stage. A no, a change request ("skip the jar one"), or a price-policy correction re-opens the draft. The save tool also refuses to run without a consent flag, so a conversation bug cannot skip it.

I did not build a pure LLM agent because I wanted every number and every branch to be testable and explainable. The cost is narrower language understanding; that is what the optional LLM layer is for.

## Where an LLM fits

The LLM layer is optional and off by default. It turns on only when LLM_API_KEY and LLM_MODEL are set in the server's .env file, and the key is never sent to the browser. It speaks the OpenAI-compatible chat-completions protocol, with Google's Gemini OpenAI-compatible endpoint as the default base URL, so Gemini, OpenAI or another compatible provider can be used by changing the environment variables.

It has two jobs and no others:

- Reword. Make the controller's draft sound like a natural phone call.
- Classify. Label an answer the rules could not read as yes, no, dont_know, not_now, repeat or other.

A guard sits between the model and the seller. A rewrite is thrown away, and the original wording is used, if it:

- changes, adds or drops any number,
- introduces a product-like name that was not in the draft,
- drops the closing question,
- claims that a price, stock level or setting was changed,
- or grows much longer than the draft.

Any error (no network, quota, wrong model name) also falls back to the rule-based reply. The model never calls a tool, never creates a plan and never does arithmetic.

Status: the guard, the fallback and the request format are covered by automated tests using fakes. It has not been run against a live provider in the environment where this was built; the repo includes a script (backend/check_llm.py) to verify a key without printing it.

## Deterministic analytics

No model produces any metric. The agent says what tested Python functions return.

change % = (current - previous) / previous x 100; AOV = GMV / orders; conversion = orders / sessions x 100.

Divisions are guarded against zero and missing values. On the demo data, orders and GMV are down 30%, sessions are down 10%, and conversion moves from 4.00% to about 3.11%.

The 150 lost orders are split arithmetically into a traffic part and a conversion part: fewer visits at the old conversion rate account for about 50 orders, and the lower conversion rate for about 100. This is a split of the numbers, not a cause, and the interface says so.

Each possible driver gets an impact, urgency and confidence rating (High = 3, Medium = 2, Low = 1) and a score of impact x 3 + urgency x 2 + confidence x 2:

| Driver | Impact | Urgency | Confidence | Score |
| --- | --- | --- | --- | --- |
| Organizer out of stock 9 days | High | High | High | 21 |
| Fewer product-page visits | High | Medium | Medium | 17 |
| Bedsheet price gap and returns | Medium | Medium | Low | 12 |
| Jar dispatch and cancellations | Low | Medium | Low | 9 |

Impact comes from the driver's share of the order drop. Confidence is deliberately low for price and fulfilment because the data cannot show that they caused the decline; they are called leads to check, not proof. The action ranking then subtracts effort. No revenue uplift is estimated anywhere. The weights are my judgment, not tuned on real outcomes.

## Alternatives considered

| Option | What it would give | Why I did not use it here |
| --- | --- | --- |
| Realtime speech-to-speech API (OpenAI Realtime over WebRTC, or Gemini Live) | Lower latency, natural interruption, better Hindi and Hinglish | Needs a paid key and ephemeral-credential plumbing; I could not test it in time, and an untested core path is a worse demo than a simple working one |
| Server-side chain: speech-to-text, LLM, text-to-speech | Better voices, one provider, audio under my control | Three provider integrations and more latency per turn; same result for the demo script |
| Full LLM tool-calling agent | Handles free-form speech much better | Harder to guarantee consent and numbers; harder to test and explain. I kept the tools and could add it on top |
| Chosen: browser speech plus rule-based controller plus optional LLM wording | Works with no key, testable, explainable | Turn-based, narrower understanding |

The tools, data and consent rule do not depend on the voice layer, so moving to a realtime API later means replacing the browser audio code, not rewriting the agent.

## Latency, interruption and limitations

I have not measured end-to-end latency. Each turn has four steps in a row: the recogniser decides the seller has stopped, the text goes to the server, the reply is built, and the browser starts speaking. Expect a noticeable pause; the server step itself is fast because it runs local Python and SQLite with no model call in the default mode.

- Interruption is manual. With open speakers the microphone would hear the agent, so listening is paused while it speaks. Use the Speak / interrupt button or Space.
- Turn-based. There is no streaming audio and no overlap.
- English replies only. A few Hinglish words are understood; the agent does not speak Hindi.
- Chrome sends the seller's audio to Google for transcription, so it needs internet.
- Understanding is rule-based by default. Unusual phrasing may get a "didn't catch that" and a repeat of the question.
- One demo seller and one pair of 30-day windows. The tools reject other windows instead of guessing.
- Data staleness is not handled. Real data would need an "as of" time in every tool result.

## Real, mocked and tested

| Part | Status |
| --- | --- |
| Voice interaction in the browser (speech in, speech out) | Real |
| Calculations, driver ranking, dialogue logic, consent rule | Real, covered by 56 automated tests |
| Plan and call-summary storage (SQLite) | Real |
| Seller, SKUs, benchmark price, targets | Synthetic, made up for this demo; not Snapdeal data or standards |
| Every action in the plan | Simulated draft; nothing is applied to any account |
| Page logic with a fake microphone and speaker (headless Chrome) | Tested |
| Real microphone and speakers | Tested by the applicant on the recording, not in the build environment |
| Live LLM provider | Not tested; off in the demo |

This is an independent prototype built for the assessment. It has no access to any Snapdeal system and is not an official Snapdeal product.
