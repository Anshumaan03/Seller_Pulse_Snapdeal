"""Headless-Chrome check of the voice UI wiring (not collected by pytest).

A real microphone and speaker cannot be tested in CI, so this injects a fake
SpeechRecognition and speechSynthesis and drives the real app.js through the demo call.
Run with the server already up:   python backend/tests/ui_smoke.py [http://localhost:8000]
"""
import os
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SHOT_DIR = os.environ.get("SHOT_DIR", "/tmp")

FAKES = """
window.__spoken = [];
window.__recs = 0;
class FakeRec {
  constructor(){ window.__rec = this; }
  start(){ window.__recs++; this.running = true; setTimeout(()=>this.onstart && this.onstart(), 5); }
  abort(){ this.running = false; }
  stop(){ this.running = false; }
}
window.SpeechRecognition = FakeRec; window.webkitSpeechRecognition = FakeRec;
window.__say = (text) => {
  const r = window.__rec;
  const res = [{transcript: text}]; res.isFinal = true;
  r.onresult({resultIndex: 0, results: [res]});
};
const fakeSynth = {
  getVoices(){ return []; }, cancel(){}, onvoiceschanged: null,
  speak(u){ if (u.text) window.__spoken.push(u.text); setTimeout(()=>u.onend && u.onend(), 5); }
};
Object.defineProperty(window, 'speechSynthesis', {value: fakeSynth, configurable: true});
"""

def wait_text(page, sel, text, timeout=8000):
    page.wait_for_function("([s,t]) => document.querySelector(s).textContent.includes(t)", arg=[sel, text], timeout=timeout)

def main():
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH", "/usr/bin/google-chrome"),
                              args=["--no-sandbox"])
        page = b.new_page(viewport={"width": 1280, "height": 1000})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.add_init_script(FAKES)
        page.goto(URL)
        page.click("#resetBtn")
        wait_text(page, "#stateText", "Ready")
        assert "Riya Home" in page.inner_text("#sellerName")
        assert "Synthetic" in page.inner_text(".top")

        page.click("#startBtn")
        page.wait_for_function("window.__spoken.length >= 3")       # greeting spoken (3 sentences)
        wait_text(page, "#stateText", "Listening")
        assert not page.is_disabled("#endBtn")
        print("greeting spoken:", " ".join(page.evaluate("window.__spoken")))

        def turn(utterance, expect_in_reply):
            before = page.evaluate("window.__spoken.length")
            page.evaluate("t => window.__say(t)", utterance)
            page.wait_for_function("n => window.__spoken.length > n", arg=before)
            wait_text(page, "#agentLine", expect_in_reply)
            wait_text(page, "#stateText", "Listening")

        turn("My orders have gone down quite a bit. I am not sure what is wrong.", "down 30%")
        turn("Yes, I can restock it in three days.", "lowest price")
        turn("I need to maintain my margin. I can review the price, but do not reduce it automatically.", "Shall I save")
        assert "Proposed plan" in page.inner_text("#planBody")
        page.screenshot(path=f"{SHOT_DIR}/ui_proposed.png")
        turn("Yes, that sounds good.", "saved in this demo")
        assert "Saved plan" in page.inner_text("#planBody")
        assert "Draft (simulated)" in page.inner_text("#planBody")
        page.click("[data-tab=transcript]")
        assert "Seller" in page.inner_text("#transcript")
        page.screenshot(path=f"{SHOT_DIR}/ui_saved.png")
        page.click("[data-tab=plan]")
        page.reload()
        wait_text(page, "#planBody", "Saved plan")                 # persisted plan is shown after a refresh
        page.click("#startBtn")                                    # new call on a persisted plan
        wait_text(page, "#stateText", "Listening")
        page.evaluate("t => window.__say(t)", "No, that's all. Thanks.")
        wait_text(page, "#stateText", "Listening")
        page.evaluate("t => window.__say(t)", "bye")
        wait_text(page, "#stateText", "Call ended")
        assert page.is_disabled("#endBtn") and not page.is_disabled("#startBtn")

        # reset clears the plan
        page.click("#resetBtn")
        wait_text(page, "#planBody", "No plan yet")
        saved = page.evaluate("fetch('/api/seller/DEMO-1042/action-plan').then(r=>r.json())")
        assert saved["items"] == [], saved

        # mic denied path shows a readable message
        page.click("#startBtn")
        wait_text(page, "#stateText", "Listening")
        page.evaluate("window.__rec.onerror({error:'not-allowed'})")
        wait_text(page, "#notice", "Microphone access is blocked")
        page.click("#endBtn")
        b.close()
    real_errors = [e for e in errors if "favicon" not in e]
    print("console/page errors:", real_errors or "none")
    assert not real_errors
    print("UI smoke test: PASS")

if __name__ == "__main__":
    main()
