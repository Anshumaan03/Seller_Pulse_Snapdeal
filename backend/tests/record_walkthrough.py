"""Record a silent, captioned walkthrough of the REAL app (headless Chrome).

This is NOT a live-voice recording. The microphone and speaker are replaced by fakes:
the 'seller' lines are scripted and fed in as text, and the agent's speech is only timed,
not played. A banner on screen says so. Use it as a README walkthrough, not as proof of
live voice. Record the real thing yourself for the submission.

Run (server already running):  python backend/tests/record_walkthrough.py http://localhost:8000 out_dir
"""
import os
import sys
import time
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/walk"
os.makedirs(OUT, exist_ok=True)

FAKES = """
window.__recs = 0;
class FakeRec {
  constructor(){ window.__rec = this; }
  start(){ window.__recs++; setTimeout(()=>this.onstart && this.onstart(), 5); }
  abort(){} stop(){}
}
window.SpeechRecognition = FakeRec; window.webkitSpeechRecognition = FakeRec;
window.__emit = (text, final) => {
  const res = [{transcript: text}]; res.isFinal = final;
  window.__rec.onresult({resultIndex: 0, results: [res]});
};
const fakeSynth = {
  getVoices(){ return []; }, cancel(){}, onvoiceschanged: null,
  // pace like real speech: roughly 3 words a second
  speak(u){ const words = (u.text||'').split(/\\s+/).filter(Boolean).length;
            setTimeout(()=>u.onend && u.onend(), Math.max(60, words * 330)); }
};
Object.defineProperty(window, 'speechSynthesis', {value: fakeSynth, configurable: true});
"""

BANNER = """
() => {
  const b = document.createElement('div');
  b.textContent = 'Automated walkthrough of the real app: scripted seller input, silent (no audio). Not a live-voice recording.';
  b.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#7c2d12;color:#fff;' +
    'font:600 15px system-ui;padding:8px 14px;text-align:center';
  document.body.appendChild(b);
}
"""

SELLER = [
    "My orders have gone down quite a bit. I am not sure what is wrong.",
    "Yes, I can restock it in three days.",
    "I need to maintain my margin. I can review the price, but do not reduce it automatically.",
    "Yes, that captures it.",
]


def wait_text(page, sel, text, timeout=60000):
    page.wait_for_function("([s,t]) => document.querySelector(s).textContent.includes(t)", arg=[sel, text], timeout=timeout)


def seller_says(page, text):
    wait_text(page, "#stateText", "Listening")
    time.sleep(1.2)                                   # a human pause before answering
    words = text.split()
    for i in range(1, len(words) + 1):               # interim words appear as they are "spoken"
        page.evaluate("t => window.__emit(t, false)", " ".join(words[:i]))
        time.sleep(0.22)
    page.evaluate("t => window.__emit(t, true)", text)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, record_video_dir=OUT,
                        record_video_size={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.add_init_script(FAKES)
    page.goto(URL)
    page.click("#resetBtn")
    wait_text(page, "#stateText", "Ready")
    page.evaluate(BANNER)
    time.sleep(2.5)                                   # let the snapshot and badges be seen

    page.click("#startBtn")
    seller_says(page, SELLER[0])
    wait_text(page, "#agentLine", "fresh stock")
    wait_text(page, "#stateText", "Listening")
    page.click("[data-tab=hood]"); time.sleep(3.0)    # show which tools were called
    page.click("[data-tab=plan]")

    seller_says(page, SELLER[1])
    wait_text(page, "#agentLine", "lowest price")
    seller_says(page, SELLER[2])
    wait_text(page, "#agentLine", "Shall I save")
    wait_text(page, "#stateText", "Listening")
    time.sleep(2.5)                                   # proposed plan on screen, nothing saved yet
    seller_says(page, SELLER[3])
    wait_text(page, "#agentLine", "saved in this demo")
    wait_text(page, "#planBody", "Saved plan")
    time.sleep(1.5)
    page.evaluate("window.scrollTo({top: 520, behavior: 'smooth'})")   # bring the saved plan into view
    time.sleep(6.0)                                   # linger on the saved, simulated plan
    video = page.video
    ctx.close()
    path = video.path()
    b.close()
print("raw video:", path)
