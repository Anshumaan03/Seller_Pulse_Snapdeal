"""Stateful dialogue controller for the Virtual KAM call.

How a turn works:
  1. Pull facts out of what the seller said (days, amounts, price policy, topics).
  2. Call backend tools for any number we are about to say.
  3. Ask only the next question whose answer would change the plan.
  4. Never save anything until the seller has said yes to a spoken, read-back draft.

Everything the agent says about the seller's business is built from tool output.
An optional LLM can reword the reply (llm.rewrite) but cannot change the numbers.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from . import tools, nlu, llm
from .analytics import format_inr, short_pct, priority_label
from .planner import short_name
from .models import ActionItem, Driver

# ---------- session ----------


@dataclass
class Session:
    session_id: str
    seller_id: str
    stage: str = "concern"          # concern -> ask -> consent -> after_plan -> ended
    facts: dict = field(default_factory=dict)
    transcript: list = field(default_factory=list)
    tool_log: list = field(default_factory=list)
    proposed: list = field(default_factory=list)   # list[ActionItem]
    plan_saved: bool = False
    ended: bool = False
    last_reply: str = ""
    turn: int = 0


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _call(s: Session, name: str, fn, *args, **kwargs):
    """Run a tool and record it for the 'under the hood' panel."""
    out = fn(*args, **kwargs)
    s.tool_log.append({"turn": s.turn, "tool": name})
    return out


def _say(s: Session, text: str) -> str:
    final = llm.rewrite(text) if llm.enabled() else text
    s.last_reply = final
    s.transcript.append({"role": "agent", "text": final, "ts": _ts()})
    return final


# ---------- helpers on data ----------


def _drivers(s: Session) -> list[Driver]:
    return _call(s, "identify_sales_drivers", tools.identify_sales_drivers, s.seller_id)


def _driver(drivers: list[Driver], prefix: str) -> Optional[Driver]:
    return next((d for d in drivers if d.driver_id.startswith(prefix)), None)


def _sku_name(data: dict, sku_id: str) -> str:
    return next(x["name"] for x in data["skus"] if x["sku_id"] == sku_id)


def _move(pct: Optional[float]) -> str:
    if pct is None:
        return "not available"
    if abs(pct) < 0.5:
        return "flat"
    return f"{'down' if pct < 0 else 'up'} {short_pct(pct, 0)}%"


# ---------- starting the call ----------


def start_call(seller_id: str) -> tuple[Session, str]:
    profile = tools.get_seller_profile(seller_id)
    s = Session(session_id=uuid.uuid4().hex[:12], seller_id=seller_id)
    s.tool_log.append({"turn": 0, "tool": "get_seller_profile"})
    greeting = (
        "Hi, this is SellerPulse, your virtual account manager. "
        "This is a prototype running on sample seller data, not a live Snapdeal account. "
        "I've compared your last 30 days with the 30 before. What change have you noticed most?"
    )
    return s, _say(s, greeting)


# ---------- questions ----------


def _pending_question(s: Session, drivers: list[Driver]) -> Optional[str]:
    """The next question whose answer would change the plan, or None."""
    f = s.facts
    pending = []
    stock = _driver(drivers, "stockout:")
    price = _driver(drivers, "price_returns:")
    if stock and f.get("restock_status") is None:
        pending.append("restock")
    if price and f.get("price_policy") is None and f.get("margin_floor") is None:
        pending.append("margin")
    # if the seller opened with the bedsheet, ask about that first
    focus = f.get("focus_sku")
    if focus and price and price.sku_id == focus and "margin" in pending:
        pending.sort(key=lambda q: 0 if q == "margin" else 1)
    return pending[0] if pending else None


def _question_text(s: Session, q: str, drivers: list[Driver]) -> str:
    data = tools.load_data(s.seller_id)
    if q == "restock":
        d = _driver(drivers, "stockout:")
        return f"Are you expecting fresh stock of the {short_name(_sku_name(data, d.sku_id))} this week?"
    d = _driver(drivers, "price_returns:")
    return f"Before we touch pricing, what's the lowest price you could accept on the {short_name(_sku_name(data, d.sku_id))}?"


def _signals_line(s: Session, drivers: list[Driver]) -> str:
    """One sentence on the other signals, said once per call."""
    if s.facts.get("signals_mentioned"):
        return ""
    data = tools.load_data(s.seller_id)
    diag = {d.sku_id: d for d in _call(s, "get_sku_diagnostics", tools.get_sku_diagnostics, s.seller_id)}
    parts = []
    p = _driver(drivers, "price_returns:")
    if p:
        d = diag[p.sku_id]
        flags = []
        if d.price_gap_pct is not None and d.price_gap_pct > 3:
            flags.append("priced above the demo benchmark")
        if d.return_gap_pp is not None and d.return_gap_pp > 3:
            flags.append("showing a higher return rate")
        parts.append(f"the {short_name(_sku_name(data, p.sku_id))} is " + " and ".join(flags))
    fu = _driver(drivers, "fulfilment:")
    if fu:
        d = diag[fu.sku_id]
        bits = []
        if d.late_dispatch_gap_pp is not None and d.late_dispatch_gap_pp > 3:
            bits.append("late dispatches")
        if d.cancellation_gap_pp is not None and d.cancellation_gap_pp > 2:
            bits.append("cancellations")
        parts.append(f"the {short_name(_sku_name(data, fu.sku_id))} has more {' and '.join(bits)} than the mock targets")
    if not parts:
        return ""
    s.facts["signals_mentioned"] = True
    n = "Another signal" if len(parts) == 1 else "Two other signals"
    return f"{n}: " + ", and ".join(parts) + "."


# ---------- diagnosis opening ----------


def _opening_findings(s: Session, concern: str, sku: Optional[str]) -> str:
    pc = _call(s, "get_period_comparison", tools.get_period_comparison, s.seller_id, "current", "previous")
    drivers = _drivers(s)
    data = tools.load_data(s.seller_id)
    p, c = pc.previous, pc.current

    if concern == "revenue":
        a = (f"I can see that. Revenue is down {short_pct(pc.gmv_change_pct, 0)}%, "
             f"from {format_inr(p.gmv)} to {format_inr(c.gmv)}.")
    elif concern == "visits":
        a = (f"Yes, page visits are {_move(pc.sessions_change_pct)}, "
             f"from {p.sessions:,} to {c.sessions:,}.")
    elif concern == "conversion":
        a = (f"Yes, conversion has slipped from {short_pct(p.conversion_pct)}% "
             f"to about {short_pct(c.conversion_pct)}%.")
    else:
        a = (f"I can see that. Orders are {_move(pc.orders_change_pct)}, "
             f"from {p.orders} to {c.orders}.")

    if concern == "visits":
        b = (f"Conversion also slipped, from {short_pct(p.conversion_pct)}% to about "
             f"{short_pct(c.conversion_pct)}%, so it isn't only traffic.")
    elif concern == "conversion":
        b = f"Visits are also {_move(pc.sessions_change_pct)}, so both moved."
    else:
        b = (f"Visits are {_move(pc.sessions_change_pct)}, but conversion also slipped from "
             f"{short_pct(p.conversion_pct)}% to about {short_pct(c.conversion_pct)}%, "
             "so traffic alone doesn't explain it.")

    c_line = ""
    focus = None
    if sku:
        for d in drivers:
            if d.sku_id == sku:
                focus = d
                break
    elif _driver(drivers, "stockout:"):
        focus = _driver(drivers, "stockout:")
    elif drivers:
        focus = drivers[0]
    if focus:
        c_line = _driver_sentence(s, focus, data, brief=True)
        if sku:
            s.facts["focus_sku"] = sku
    return " ".join(x for x in (a, b, c_line) if x)


def _driver_sentence(s: Session, d: Driver, data: dict, brief: bool = False) -> str:
    diag = {x.sku_id: x for x in tools.get_sku_diagnostics(s.seller_id)}
    if d.driver_id.startswith("stockout:"):
        x = diag[d.sku_id]
        if brief:
            return f"The {x.name} was out of stock for {x.stockout_days} days."
        return (f"The {x.name} was out of stock for {x.stockout_days} days "
                f"and its orders fell {short_pct(x.orders_change_pct, 0)}%.")
    if d.driver_id.startswith("price_returns:"):
        x = diag[d.sku_id]
        bits = [f"orders are {_move(x.orders_change_pct)}"]
        if x.price_gap_pct is not None and x.price_gap_pct > 3:
            bits.append(f"it's listed at {format_inr(x.selling_price)} against a demo benchmark of "
                        f"{format_inr(x.benchmark_price)}")
        if x.return_gap_pp is not None and x.return_gap_pp > 3:
            bits.append(f"returns are {short_pct(x.return_rate_pct, 0)}% against a {short_pct(x.return_rate_pct - x.return_gap_pp, 0)}% baseline")
        return f"On the {x.name}, " + ", ".join(bits) + "."
    if d.driver_id.startswith("fulfilment:"):
        x = diag[d.sku_id]
        return (f"On the {x.name}, late dispatch is {short_pct(x.late_dispatch_rate_pct, 0)}% against a mock target of "
                f"{short_pct(data['targets']['late_dispatch_rate_pct'], 0)}%, and cancellations are "
                f"{short_pct(x.cancellation_rate_pct, 0)}% against {short_pct(data['targets']['cancellation_rate_pct'], 0)}%.")
    return "Page visits dipped, but this data can't tell me why."


def _explain(s: Session, text: str) -> str:
    drivers = _drivers(s)
    data = tools.load_data(s.seller_id)
    sku = nlu.mentioned_sku(text)
    d = next((x for x in drivers if sku and x.sku_id == sku), None)
    if d is None and nlu.has_any(text, ["traffic", "visits", "visit", "sessions"]):
        d = _driver(drivers, "traffic")
    if d is None:
        d = drivers[0] if drivers else None
    if d is None:
        return "I don't see a clear signal in this data."
    tail = {
        "stockout": "That fits a stockout effect, but it isn't proof that it's the only cause.",
        "price_returns": "That's a lead worth testing, not proof of the cause.",
        "fulfilment": "That could hurt repeat orders, but I can't show that from this data.",
        "traffic": "I can't tell from this data why visits fell.",
    }[d.driver_id.split(":")[0]]
    if d.driver_id == "traffic":
        pc = tools.get_period_comparison(s.seller_id)
        facts = (f"Visits are {_move(pc.sessions_change_pct)}, which by simple arithmetic accounts for about "
                 f"{round(pc.orders_lost_from_traffic)} of the {pc.orders_lost_total} lost orders.")
        return f"{facts} {tail}"
    return f"{_driver_sentence(s, d, data)} {tail}"


# ---------- proposing the plan ----------

_DRIVER_FOR_KEY = {
    "restock": "stockout:", "returns_review": "price_returns:", "price_review": "price_returns:",
    "price_test": "price_returns:", "dispatch_fix": "fulfilment:", "traffic_check": "traffic",
}


def _build_proposals(s: Session) -> list[ActionItem]:
    from .planner import build_candidate_actions
    data = tools.load_data(s.seller_id)
    drivers = _drivers(s)
    items = build_candidate_actions(data, drivers, s.facts)
    items = [i for i in items if i.key not in s.facts.get("removed", set())]
    constraints = {"price_policy": s.facts.get("price_policy"), "margin_floor": s.facts.get("margin_floor")}
    scored = []
    for i in items:
        ev = _driver(drivers, _DRIVER_FOR_KEY[i.key])
        pr = _call(s, "estimate_action_priority", tools.estimate_action_priority, i, ev, constraints)
        i = i.model_copy(update={"priority": priority_label(pr.score),
                                 "rationale": i.rationale or pr.rank_reason})
        scored.append((pr.score, i))
    scored.sort(key=lambda t: -t[0])         # stable: ties keep build order
    s.proposed = [i for _, i in scored]
    return s.proposed


def _spoken(i: ActionItem) -> str:
    return i.spoken or i.title[0].lower() + i.title[1:]


def _join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def _spoken_with_time(i: ActionItem) -> str:
    t = _spoken(i)
    return t if (i.key == "restock" and i.kind == "inventory") else f"{t}, {i.timeframe.lower()}"


def _present_plan(s: Session, lead: str = "Here's the draft plan.") -> str:
    s.stage = "consent"
    listed = _join([_spoken(i) for i in s.proposed[:6]])
    return (f"{lead} {listed[0].upper() + listed[1:]}. "
            "It's a simulated draft, nothing changes on any live account. Shall I save this plan?")


def _advance(s: Session, preface: str) -> str:
    drivers = _drivers(s)
    q = _pending_question(s, drivers)
    if q:
        s.stage = "ask"
        s.facts["pending"] = q
        extra = _signals_line(s, drivers) if q == "margin" else ""
        return " ".join(x for x in (preface, extra, _question_text(s, q, drivers)) if x)
    s.facts["pending"] = None
    _build_proposals(s)
    if not s.proposed:
        s.stage = "after_plan"
        return (preface + " I don't see anything that needs an action yet. "
                "Anything else you'd like to look at?").strip()
    return _present_plan(s, (preface + " Here's the draft plan.").strip())


# ---------- slot filling ----------


def _fill_slots(s: Session, text: str) -> set[str]:
    f, changed = s.facts, set()
    pending = f.get("pending")

    status, days = nlu.extract_restock(text, asked=(pending == "restock"))
    if status is not None and (f.get("restock_status") != status or f.get("restock_days") != days):
        f["restock_status"], f["restock_days"] = status, days
        changed.add("restock")

    wants_price = pending == "margin" or nlu.has_any(
        text, ["price", "pricing", "minimum", "margin", "lowest", "floor", "at least", "reduce", "discount"])
    if wants_price:
        amt = nlu.extract_amount(text, expect_amount=(pending == "margin"))
        if amt is not None and f.get("margin_floor") != amt:
            f["margin_floor"] = amt
            changed.add("price")
        pol = nlu.extract_price_policy(text)
        if pol is None and amt is not None and f.get("price_policy") is None:
            pol = "open"
        if pol is None and pending == "margin" and (
                nlu.is_dont_know(text) or nlu.has_any(text, ["maintain my margin", "margin is tight", "tight margin",
                                                             "low margin", "thin margin", "need my margin"])):
            pol = "unknown"
        if pol is not None and f.get("price_policy") != pol:
            f["price_policy"] = pol
            changed.add("price")

    cause = nlu.extract_dispatch_cause(text)
    if cause and f.get("dispatch_cause") != cause:
        f["dispatch_cause"] = cause
        changed.add("dispatch")
    return changed


def _ack(s: Session, changed: set[str]) -> str:
    f = s.facts
    out = []
    if "restock" in changed:
        st, d = f.get("restock_status"), f.get("restock_days")
        if st == "soon":
            out.append(f"Good, about {d} days is workable, and that gives us a practical first step."
                       if d else "Good, that gives us a practical first step.")
        elif st == "none":
            out.append("Understood. Then we'll plan around the stockout instead.")
        else:
            out.append("No problem, we'll make confirming a restock date the first step.")
    if "price" in changed:
        pol, floor = f.get("price_policy"), f.get("margin_floor")
        data = tools.load_data(s.seller_id)
        price = next((x["selling_price"] for x in data["skus"] if x.get("selling_price")), None)
        if pol == "manual_only":
            out.append("Understood, I won't change any price. I'll only draft a review for you to decide.")
        elif pol == "no_cut":
            out.append("Understood, no price reduction. We'll look at returns and the listing instead.")
        elif pol == "unknown":
            out.append("That's fine, we'll keep price out of the plan until you've checked your margin.")
        elif floor is not None and price is not None and floor < price:
            out.append(f"Thanks, {format_inr(floor)} leaves some room below {format_inr(price)}, "
                       "but I'll only draft a test for your approval.")
        elif floor is not None:
            out.append(f"Thanks. {format_inr(floor)} leaves no room to cut, so we'll focus on returns.")
    if "dispatch" in changed:
        out.append(f"Noted, {f['dispatch_cause']} on the dispatch side.")
    return " ".join(out)


# ---------- saving / closing ----------


def _save_plan(s: Session) -> str:
    plan = _call(s, "create_action_plan", tools.create_action_plan, s.seller_id, s.proposed, True)
    s.plan_saved = True
    s.stage = "after_plan"
    first = min(plan.items, key=lambda i: (i.due_date or "9999",))
    return ("Done. The plan is saved in this demo, not applied to a live Snapdeal account. "
            f"First checkpoint: {_spoken_with_time(first)}. Anything else before we end?")


def _close(s: Session, reason: str = "done") -> str:
    pc = tools.get_period_comparison(s.seller_id)
    plan = _call(s, "get_action_plan", tools.get_action_plan, s.seller_id)
    decisions = [i.title for i in plan.items] if s.plan_saved else []
    disputes = s.facts.get("disputes", [])
    summary = (f"Seller reported lower sales. Orders {_move(pc.orders_change_pct)} "
               f"({pc.previous.orders} to {pc.current.orders}), visits {_move(pc.sessions_change_pct)}, "
               f"conversion {short_pct(pc.previous.conversion_pct)}% to {short_pct(pc.current.conversion_pct)}%. "
               + ("Draft action plan agreed (simulated)." if s.plan_saved else "No plan was saved on this call.")
               + (f" Seller questioned a figure: {'; '.join(disputes)}." if disputes else ""))
    first = min(plan.items, key=lambda i: (i.due_date or "9999",)) if plan.items else None
    follow_up = (f"Check in on: {first.title} ({first.timeframe})" if first else "Revisit when the seller is ready.")
    _call(s, "log_call_summary", tools.log_call_summary, s.seller_id, summary, decisions, follow_up)
    s.stage, s.ended = "ended", True
    if s.plan_saved and first:
        return (f"Quick recap: orders are down {short_pct(pc.orders_change_pct, 0)}%, and we agreed "
                f"{len(plan.items)} draft actions, starting with: {_spoken_with_time(first)}. "
                "We'll review availability, orders and dispatch at the next check-in. Thanks!")
    if reason == "not_now":
        return ("Understood, no problem. I've noted what we found and saved no plan, so nothing has changed. "
                "We can pick this up whenever you're ready.")
    return ("Okay, I've noted the findings. No plan was saved, so nothing has changed. "
            "We can pick this up whenever you're ready.")


_PROMO_REPLY = ("I'd hold off on ads or discounts for now, because the dispatch and cancellation misses are better fixed "
                "before we send more demand. I won't create any promotion without your approval, and I can't promise "
                "it would lift sales.")


def _reask(s: Session) -> str:
    if s.stage == "ask":
        return _question_text(s, s.facts["pending"], _drivers(s))
    if s.stage == "consent":
        return "Shall I save the plan?"
    return ""


def _llm_label(text: str) -> str:
    return llm.classify(text) if llm.enabled() else "other"


# ---------- the turn ----------


def handle_turn(s: Session, text: str) -> str:
    text = (text or "").strip()
    if s.ended:
        return "This call has ended. Start a new call to continue."
    if not text:
        return "I didn't catch that. Could you say it once more?"
    s.turn += 1
    s.transcript.append({"role": "seller", "text": text, "ts": _ts()})
    reply = _route(s, text)
    return _say(s, reply)


def _route(s: Session, text: str) -> str:
    f = s.facts

    if nlu.is_repeat(text):
        return "Sure. " + (s.last_reply or "")
    if nlu.has_any(text, ["bye", "goodbye", "end the call", "end call", "hang up"]) and s.stage != "after_plan":
        return _close(s, "early")
    if nlu.is_not_now(text):
        return _close(s, "not_now")
    if nlu.is_wrong_number(text) and s.stage != "concern":
        f.setdefault("disputes", []).append(text[:80])
        return ("Thanks for flagging that. These figures come from the demo data file, and I can't edit that data "
                "from here, but I've noted it for review. "
                + _reask(s)).strip()

    stage = s.stage

    if stage == "concern":
        concern = nlu.classify_concern(text)
        sku = nlu.mentioned_sku(text)
        if concern == "unclear" and not sku and not nlu.is_explain(text) and f.get("concern_retries", 0) < 1:
            f["concern_retries"] = 1
            return ("I'm here to look at your sales. Is the main worry orders, revenue or page visits?")
        f["concern"] = concern if concern != "unclear" else "orders"
        # take in anything useful the seller already volunteered
        changed = _fill_slots(s, text)
        opening = _opening_findings(s, f["concern"], sku)
        return _advance(s, " ".join(x for x in (opening, _ack(s, changed)) if x))

    if stage == "ask":
        pending = f.get("pending")
        changed = _fill_slots(s, text)
        if nlu.is_promo(text):
            return _PROMO_REPLY + " " + _reask(s)
        if nlu.is_explain(text) and not changed:
            return _explain(s, text) + " " + _reask(s)
        if not changed:
            if pending == "restock" and nlu.is_dont_know(text):
                f["restock_status"], f["restock_days"] = "unknown", None
                changed.add("restock")
            elif pending == "margin" and nlu.is_dont_know(text):
                f["price_policy"] = "unknown"
                changed.add("price")
        if not changed:
            label = _llm_label(text)
            if label == "dont_know":
                if pending == "restock":
                    f["restock_status"], f["restock_days"] = "unknown", None
                else:
                    f["price_policy"] = "unknown"
                changed.add("restock" if pending == "restock" else "price")
            elif label == "no" and pending == "restock":
                f["restock_status"], f["restock_days"] = "none", None
                changed.add("restock")
        if not changed:
            return "Sorry, I didn't quite catch that. " + _reask(s)
        return _advance(s, _ack(s, changed))

    if stage == "consent":
        removal = nlu.extract_removal(text)
        changed = _fill_slots(s, text)
        if removal:
            f.setdefault("removed", set()).update(removal)
            _build_proposals(s)
            if not s.proposed:
                s.stage = "after_plan"
                return ("Understood, I've taken everything out and saved nothing. "
                        "Anything else you'd like to look at?")
            return _present_plan(s, "Got it, I've taken that out. Here's the updated draft.")
        if changed:
            _build_proposals(s)
            return _present_plan(s, _ack(s, changed) + " Here's the updated draft.")
        if nlu.is_no(text):
            return "No problem, nothing is saved. Which part should I drop or change?"
        if nlu.is_yes(text):
            return _save_plan(s)
        if nlu.is_promo(text):
            return _PROMO_REPLY + " Shall I save the draft plan?"
        if nlu.is_explain(text) or nlu.mentioned_sku(text):
            return _explain(s, text) + " Shall I save the plan?"
        if nlu.is_dont_know(text):
            return "No rush. I can read the draft again, or you can tell me what to change."
        label = _llm_label(text)
        if label == "yes":
            return _save_plan(s)
        if label == "no":
            return "No problem, nothing is saved. Which part should I drop or change?"
        return "Sorry, should I save this draft plan? You can say yes, or tell me what to change."

    if stage == "after_plan":
        if nlu.is_recap(text):
            plan = _call(s, "get_action_plan", tools.get_action_plan, s.seller_id)
            if not plan.items:
                return "There's no saved plan yet. Anything else you'd like to look at?"
            return f"Here's the saved plan, still a simulated draft: {_join([_spoken(i) for i in plan.items[:6]])}. Anything else?"
        removal = nlu.extract_removal(text)
        if removal and s.plan_saved:
            plan = tools.get_action_plan(s.seller_id)
            keep = [i for i in plan.items if i.key not in removal]
            if keep:
                tools.create_action_plan(s.seller_id, keep, consent_confirmed=True)
                s.proposed = keep
                return f"Done, I've taken that out of the saved plan. {len(keep)} items remain. Anything else?"
        if nlu.is_promo(text):
            return _PROMO_REPLY
        if nlu.is_explain(text) or nlu.mentioned_sku(text):
            return _explain(s, text) + " Anything else?"
        if nlu.is_goodbye(text) or nlu.is_no(text):
            return _close(s)
        if nlu.is_yes(text):
            return "Sure, what else would you like to cover?"
        return "Happy to help. Shall I go over the plan again, or shall we end the call?"

    return "Could you say that again?"


# ---------- what the API exposes ----------


def public_facts(s: Session) -> dict:
    f = dict(s.facts)
    f["removed"] = sorted(f.get("removed", []))
    return f
