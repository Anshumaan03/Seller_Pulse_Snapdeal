# Submission email draft

**To:** Sourav Chakraborty
**Subject:** AI First Intern assignment: SellerPulse (Virtual KAM voice prototype) - [Your Name]

---

Hi Sourav,

Thank you for the opportunity. Please find my submission for the Virtual KAM assignment.

**What I built:** SellerPulse is a voice-first Virtual KAM. The seller speaks to it about a sales drop. It compares the last 30 days with the 30 before, splits the decline into traffic and conversion, checks each product for stockouts, price gaps, returns and fulfilment misses, asks the one or two questions that change the advice, and ends with a prioritised action plan the seller has to approve out loud. Nothing is saved without a yes, and everything it creates is a simulated draft.

**Links**
- Screen recording (about [90-110] seconds): [RECORDING LINK]
- Working demo: [DEMO LINK, or write: "runs locally in Chrome; I'm happy to demo it live"]
- Code and docs: [REPO / ZIP LINK]
- Model and voice note: attached (`model-and-voice-note.md`), also in the repo under `docs/`

**Stack, in short:** browser speech recognition and speech synthesis for voice, a FastAPI backend, a Python dialogue controller that calls typed tools, and ordinary tested functions for all the numbers. [Add one line only if true: "An optional LLM (<model name>) rewords replies; it cannot change any figure."]

**How I approached it:** I wanted the agent to behave like a KAM who has already looked at the account, so every metric comes from deterministic Python tools and not from a model. The agent separates what the data shows from what is only a hypothesis, asks permission before drafting anything consequential, and records what was agreed.

**Please note**
- All seller data, the benchmark price and the targets are synthetic and made up for this demo. They are not Snapdeal data or Snapdeal standards.
- It is an independent prototype with no access to any Snapdeal system.
- Voice uses Chrome's built-in speech, so it is turn-based and does not yet interrupt automatically. A realtime speech-to-speech API is the next step I would take.
- I used AI tools while building this, as the brief allows. [Optional: add one sentence on what you decided or changed yourself.]

I would be glad to walk through the design and do a live demo whenever suits you.

Regards,
[Your Name]
[Phone] | [Email] | [LinkedIn / GitHub]

---

### Before you send

- [ ] Every link opens in a private window.
- [ ] The recording plays with sound.
- [ ] Remove every bracketed placeholder.
- [ ] Do not write that it is deployed unless you have actually deployed it and tested the microphone on that URL.
- [ ] Check the real deadline in Sourav's email timestamp. The email mentions both 24 and 48 hours; do not rely on either until you confirm.
