// SellerPulse front end. Voice = browser speech recognition (in) + speech synthesis (out).
// The server owns the conversation and all numbers; this file only handles audio and display.
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const synth = window.speechSynthesis;

  const els = {
    stateDot: $("stateDot"), stateText: $("stateText"), agentLine: $("agentLine"), liveLine: $("liveLine"),
    start: $("startBtn"), speak: $("speakBtn"), mic: $("micBtn"), spk: $("spkBtn"), end: $("endBtn"),
    notice: $("notice"), transcript: $("transcript"), planBody: $("planBody"),
    toolLog: $("toolLog"), facts: $("factsBox"), mode: $("modeBox"),
    typedForm: $("typedForm"), typedInput: $("typedInput"),
  };

  const S = {
    sellerId: "DEMO-1042", sessionId: null, active: false, busy: false,
    micMuted: false, spkMuted: false, rec: null, heard: false, retries: 0,
    speakToken: 0, listenToken: 0, voice: null, config: null,
  };

  const STATES = {
    idle: "Ready to call", connecting: "Connecting…", listening: "Listening…",
    thinking: "Thinking…", speaking: "Speaking…", ended: "Call ended", muted: "Mic muted",
  };

  function setState(key) {
    els.stateDot.className = "dot " + (key === "muted" ? "idle" : key);
    els.stateText.textContent = STATES[key] || key;
  }
  function notice(msg, info) {
    els.notice.hidden = !msg;
    els.notice.textContent = msg || "";
    els.notice.className = "notice" + (info ? " info" : "");
  }
  function setControls(inCall) {
    els.start.disabled = inCall;
    [els.speak, els.mic, els.spk, els.end].forEach((b) => (b.disabled = !inCall));
  }

  // ---------- data panels ----------
  const inr = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
  const num = (n) => Math.round(n).toLocaleString("en-IN");
  const pct = (n, d = 1) => (n == null ? "n/a" : n.toFixed(d) + "%");
  function change(n, suffix = "%", d = 0) {
    if (n == null) return "n/a";
    const cls = n < 0 ? "neg" : n > 0 ? "pos" : "";
    return `<span class="${cls}">${n > 0 ? "+" : ""}${n.toFixed(d)}${suffix}</span>`;
  }

  async function api(path, opts) {
    const r = await fetch(path, opts && opts.body ? {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(opts.body),
    } : opts);
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json()).detail || detail; } catch (e) { /* ignore */ }
      throw new Error(detail);
    }
    return r.json();
  }

  async function loadSnapshot() {
    const [snap, diag, cfg] = await Promise.all([
      api(`/api/seller/${S.sellerId}/snapshot`), api(`/api/seller/${S.sellerId}/diagnosis`), api("/api/config"),
    ]);
    S.config = cfg;
    const p = snap.profile, c = snap.comparison;
    $("sellerName").textContent = p.name;
    $("sellerMeta").textContent = `${p.seller_id} · ${p.category} · ${p.current_window} vs ${p.previous_window}`;
    $("windowNote").textContent = `${p.current_window} compared with ${p.previous_window}`;
    $("snapTable").querySelector("tbody").innerHTML =
      `<tr><th></th><th>Before</th><th>Now</th><th>Change</th></tr>` +
      `<tr><td>GMV</td><td>${inr(c.previous.gmv)}</td><td>${inr(c.current.gmv)}</td><td>${change(c.gmv_change_pct)}</td></tr>` +
      `<tr><td>Orders</td><td>${num(c.previous.orders)}</td><td>${num(c.current.orders)}</td><td>${change(c.orders_change_pct)}</td></tr>` +
      `<tr><td>Sessions</td><td>${num(c.previous.sessions)}</td><td>${num(c.current.sessions)}</td><td>${change(c.sessions_change_pct)}</td></tr>` +
      `<tr><td>Conversion</td><td>${pct(c.previous.conversion_pct, 2)}</td><td>${pct(c.current.conversion_pct, 2)}</td><td>${change(c.conversion_change_pp, " pp", 2)}</td></tr>` +
      `<tr><td>AOV</td><td>${inr(c.previous.aov)}</td><td>${inr(c.current.aov)}</td><td>${change(c.aov_change_pct)}</td></tr>`;
    $("reconNote").textContent = snap.reconciliation_problems.length
      ? "Data check: " + snap.reconciliation_problems.join("; ")
      : `Data check passed: SKU orders add up to the account totals. Of the ${c.orders_lost_total} lost orders, about ` +
        `${Math.round(c.orders_lost_from_traffic)} follow from fewer visits and ${Math.round(c.orders_lost_from_conversion)} from lower conversion (arithmetic split, not a cause).`;
    $("targetsNote").textContent = snap.targets_note;

    $("signals").innerHTML = diag.drivers.map((d) => `
      <div class="sig">
        <h3>${esc(d.title)}</h3>
        <ul>${d.observed_facts.map((f) => `<li><span class="tag obs">Observed</span>${esc(f)}</li>`).join("")}</ul>
        <div><span class="tag hyp">Hypothesis</span>${esc(d.likely_explanation)}</div>
        <details><summary>To verify &middot; impact ${d.impact}, confidence ${d.confidence}</summary>
          <ul>${d.to_verify.map((q) => `<li><span class="tag ver">Ask</span>${esc(q)}</li>`).join("")}</ul>
          ${d.missing_data.length ? `<div class="small">Missing data: ${esc(d.missing_data.join("; "))}</div>` : ""}
        </details>
      </div>`).join("");
    els.mode.textContent = JSON.stringify({
      voice: "browser speech recognition + speech synthesis",
      recognition_supported: !!SR, synthesis_supported: !!synth,
      llm: cfg.llm,
    }, null, 2);
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function renderPlan(data) {
    const saved = data.plan && data.plan.items && data.plan.items.length;
    const items = saved ? data.plan.items : data.proposed || [];
    if (!items.length) {
      els.planBody.innerHTML = `<p class="muted">No plan yet. It appears here once the agent proposes one, and is saved only after the seller says yes.</p>`;
      return;
    }
    const head = saved
      ? `<div class="planhead">Saved plan <span class="muted small">(simulated draft, consent recorded)</span></div>`
      : `<div class="planhead">Proposed plan <span class="muted small">(waiting for the seller's yes, nothing saved)</span></div>`;
    els.planBody.innerHTML = head + `<div class="plan-wrap"><table class="plan"><thead><tr>
      <th>Priority</th><th>Action</th><th>Owner</th><th>When</th><th>Success metric</th><th>Status</th><th>Consent</th></tr></thead><tbody>` +
      items.map((i) => `<tr>
        <td><span class="pri ${i.priority}">${i.priority}</span></td>
        <td><b>${esc(i.title)}</b><div class="muted small">${esc(i.detail)}</div></td>
        <td>${esc(i.owner)}</td>
        <td>${esc(i.timeframe)}${i.due_date ? `<div class="muted small">by ${esc(i.due_date)}</div>` : ""}</td>
        <td class="small">${esc(i.success_metric)}</td>
        <td>${saved ? esc(i.status) : "Proposed"}</td>
        <td>${saved ? esc(i.consent) : "Not yet asked"}</td></tr>`).join("") + `</tbody></table></div>`;
  }

  function renderTranscript(list) {
    if (!list.length) return;
    els.transcript.innerHTML = list.map((t) =>
      `<div class="line ${t.role}"><span class="who">${t.role === "agent" ? "SellerPulse" : "Seller"}</span>${esc(t.text)}</div>`).join("");
    els.transcript.scrollTop = els.transcript.scrollHeight;
  }

  function renderHood(data) {
    const byTurn = {};
    (data.tool_log || []).forEach((t) => (byTurn[t.turn] = (byTurn[t.turn] || []).concat(t.tool)));
    els.toolLog.innerHTML = Object.keys(byTurn).map((k) =>
      `<div><span class="muted small">turn ${k}:</span> ${byTurn[k].map((t) => `<span class="chip">${t}</span>`).join(" ")}</div>`).join("");
    els.facts.textContent = JSON.stringify(data.facts || {}, null, 2);
  }

  function applyTurn(data) {
    renderPlan(data); renderTranscript(data.transcript || []); renderHood(data);
    els.agentLine.textContent = data.reply;
  }

  // ---------- speech out ----------
  function pickVoice() {
    const voices = synth ? synth.getVoices() : [];
    S.voice = voices.find((v) => v.lang === "en-IN") || voices.find((v) => /en[-_]IN/i.test(v.lang))
      || voices.find((v) => v.lang && v.lang.startsWith("en-GB")) || voices.find((v) => v.lang && v.lang.startsWith("en")) || null;
  }
  if (synth) { pickVoice(); synth.onvoiceschanged = pickVoice; }

  // Speak sentence by sentence: long single utterances get cut off in some Chrome voices.
  function speak(text) {
    return new Promise((resolve) => {
      if (!synth || S.spkMuted) return resolve();
      const token = ++S.speakToken;
      synth.cancel();
      const parts = text.match(/[^.?!]+[.?!]*/g) || [text];
      let i = 0;
      const next = () => {
        if (token !== S.speakToken || i >= parts.length) return resolve();
        const u = new SpeechSynthesisUtterance(parts[i++].trim());
        if (S.voice) { u.voice = S.voice; u.lang = S.voice.lang; } else { u.lang = "en-IN"; }
        u.rate = 1.1;   // slightly brisk so the whole demo fits in two minutes
        u.onend = next;
        u.onerror = () => resolve();
        synth.speak(u);
      };
      next();
    });
  }
  function stopSpeaking() { S.speakToken++; if (synth) synth.cancel(); }

  // ---------- speech in ----------
  function stopListening() {
    S.listenToken++;
    if (S.rec) { try { S.rec.abort(); } catch (e) { /* already stopped */ } S.rec = null; }
    els.liveLine.textContent = "";
  }

  function listen() {
    if (!S.active || S.busy || S.micMuted) return;
    if (!SR) {
      setState("listening");
      notice("This browser has no speech recognition. Use Chrome or Edge on localhost, or the typed box below.", true);
      return;
    }
    stopListening();
    const token = S.listenToken;
    const rec = new SR();
    S.rec = rec; S.heard = false;
    rec.lang = "en-IN"; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;

    rec.onstart = () => { if (token === S.listenToken) setState("listening"); };
    rec.onresult = (ev) => {
      if (token !== S.listenToken) return;
      let interim = "", final = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        (r.isFinal ? (final += r[0].transcript) : (interim += r[0].transcript));
      }
      els.liveLine.textContent = interim || final;
      if (final.trim()) { S.heard = true; S.retries = 0; notice(""); sendText(final.trim()); }
    };
    rec.onerror = (ev) => {
      if (token !== S.listenToken) return;
      const e = ev.error;
      if (e === "no-speech" || e === "aborted") return;           // onend handles the retry
      S.heard = true;                                              // stop the auto-retry loop
      const msgs = {
        "not-allowed": "Microphone access is blocked. Click the lock icon next to the address, allow the microphone, then press Start call again.",
        "service-not-allowed": "Speech recognition is blocked for this page. Check the site permissions in Chrome.",
        "audio-capture": "No microphone was found. Plug one in or pick one in your system sound settings.",
        "network": "Chrome's speech service could not be reached. Check your internet connection (Chrome sends audio to Google for transcription).",
        "language-not-supported": "This browser does not support that speech language.",
      };
      setState("idle");
      notice(msgs[e] || `Speech recognition error: ${e}. You can use the typed box instead.`);
    };
    rec.onend = () => {
      if (token !== S.listenToken || S.heard || !S.active || S.busy || S.micMuted) return;
      // nothing was transcribed: try again twice, then wait for the user
      if (S.retries < 2) { S.retries++; setTimeout(() => token === S.listenToken && listen(), 250); }
      else {
        S.retries = 0;
        setState("idle");
        notice("I'm not hearing anything. Check your microphone, then press Speak / interrupt.", true);
      }
    };
    try { rec.start(); } catch (e) { notice("Could not start the microphone: " + e.message); }
  }

  // ---------- conversation ----------
  async function sendText(text) {
    if (!S.active || S.busy) return;
    S.busy = true; stopListening();
    els.liveLine.textContent = "You: " + text;
    setState("thinking");
    try {
      const data = await api(`/api/call/${S.sessionId}/message`, { body: { text } });
      applyTurn(data);
      setState("speaking");
      await speak(data.reply);
      S.busy = false;
      if (data.call_ended) return finishCall();
      listen();
    } catch (err) {
      S.busy = false;
      notice("Could not reach the SellerPulse server: " + err.message);
      setState("idle");
    }
  }

  async function startCall() {
    notice("");
    if (!SR) notice("Voice input needs Chrome or Edge. You will still hear the agent; use the typed box to reply.", true);
    if (synth) synth.speak(new SpeechSynthesisUtterance(""));   // unlock audio inside the click gesture
    setState("connecting"); setControls(true);
    S.active = true; S.busy = true;
    try {
      const data = await api("/api/call/start", { body: { seller_id: S.sellerId } });
      S.sessionId = data.session_id;
      applyTurn(data);
      setState("speaking");
      await speak(data.reply);
      S.busy = false;
      listen();
    } catch (err) {
      S.active = false; S.busy = false; setControls(false); setState("idle");
      notice("Could not start the call: " + err.message);
    }
  }

  function finishCall() {
    S.active = false; stopListening(); stopSpeaking();
    setState("ended"); setControls(false);
    els.liveLine.textContent = "";
  }

  async function endCall() {
    if (S.sessionId && S.active) {
      try { applyTurn(await api(`/api/call/${S.sessionId}/end`, { body: {} })); } catch (e) { /* ignore */ }
    }
    finishCall();
    els.agentLine.textContent = "Call ended. The transcript and any saved plan stay on screen until you reset the demo.";
  }

  async function resetDemo() {
    finishCall();
    try { await api("/api/reset", { body: { seller_id: S.sellerId } }); } catch (e) { notice(e.message); return; }
    S.sessionId = null; S.busy = false;
    setState("idle"); notice("");
    els.agentLine.innerHTML = "Press <b>Start call</b> and allow the microphone when Chrome asks.";
    els.transcript.innerHTML = `<p class="muted">The transcript is a supporting aid. It fills in as you talk.</p>`;
    els.toolLog.innerHTML = ""; els.facts.textContent = "{}";
    renderPlan({});
  }

  // ---------- wiring ----------
  els.start.onclick = startCall;
  els.end.onclick = endCall;
  $("resetBtn").onclick = resetDemo;
  $("demoBtn").onclick = () => { S.sellerId = $("sellerSelect").value; loadSnapshot().catch((e) => notice(e.message)); };
  els.speak.onclick = () => { stopSpeaking(); if (!S.busy) { S.micMuted = false; syncMic(); listen(); } };
  els.mic.onclick = () => { S.micMuted = !S.micMuted; syncMic(); if (S.micMuted) { stopListening(); setState("muted"); } else listen(); };
  els.spk.onclick = () => { S.spkMuted = !S.spkMuted; els.spk.setAttribute("aria-pressed", S.spkMuted); els.spk.textContent = S.spkMuted ? "Unmute speaker" : "Mute speaker"; if (S.spkMuted) stopSpeaking(); };
  function syncMic() { els.mic.setAttribute("aria-pressed", S.micMuted); els.mic.textContent = S.micMuted ? "Unmute mic" : "Mute mic"; }
  els.typedForm.onsubmit = (e) => { e.preventDefault(); const t = els.typedInput.value.trim(); if (t && S.active) { els.typedInput.value = ""; stopSpeaking(); sendText(t); } };
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && S.active && !/INPUT|TEXTAREA|BUTTON|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); els.speak.click(); }
  });
  document.querySelectorAll(".tab").forEach((t) => t.onclick = () => {
    document.querySelectorAll(".tab").forEach((x) => { x.classList.toggle("active", x === t); x.setAttribute("aria-selected", x === t); });
    ["plan", "transcript", "hood"].forEach((n) => ($("tab-" + n).hidden = n !== t.dataset.tab));
  });

  // test hook (used by the headless UI check, harmless in normal use)
  window.__sellerpulse = { state: S };

  setState("idle");
  loadSnapshot().catch((e) => notice("Could not load the demo data: " + e.message));
  // a plan saved earlier in this demo session (stored in SQLite) is shown straight away
  api(`/api/seller/${S.sellerId}/action-plan`).then((plan) => renderPlan({ plan })).catch(() => {});
})();
