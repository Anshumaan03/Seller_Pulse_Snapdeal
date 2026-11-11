import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from app import llm  # noqa: E402

if not llm.enabled():
    sys.exit("LLM is off: set LLM_API_KEY and LLM_MODEL in .env (see .env.example).")

info = llm.info()
print(f"Model: {info['model']}\nEndpoint: {info['base_url']}")
draft = "Orders are down 30%, from 500 to 350. Are you expecting fresh stock of the organizer this week?"
try:
    raw = llm._chat([
        {"role": "system", "content": llm.KAM_SYSTEM_PROMPT},
        {"role": "user", "content": f"{llm.REWRITE_INSTRUCTION}\n\nDRAFT:\n{draft}"},
    ])
except Exception as e:  # network, bad key, wrong model name, quota
    sys.exit(f"Call failed: {type(e).__name__}: {e}")
print("\nDraft    :", draft)
print("Rewritten:", raw)
print("Guard    :", "PASS - this rewrite would be used" if llm.guard_ok(draft, raw)
      else "REJECTED - the app would fall back to the original wording (that is the guard doing its job)")
print("Classify :", llm.classify("hmm, I'm not really sure about that"), "(expect dont_know or other)")
