"""Small rule-based language understanding for the dialogue controller.

Deliberately simple and readable: keyword and regex rules, English plus a few
common Hinglish words. Speech-to-text hands us plain text; we pull out intent
and slots (days, rupee amounts, price policy, SKU mentions).
"""
import re
from typing import Optional

_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "a": 1, "an": 1,
}
_UNIT_DAYS = {"day": 1, "days": 1, "din": 1, "dino": 1, "week": 7, "weeks": 7, "hafta": 7, "hafte": 7, "haftey": 7}


def norm(text: str) -> str:
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"[^\w\s₹.,'%-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def tokens(text: str) -> list[str]:
    return re.findall(r"[\w₹']+", norm(text))


def has_any(text: str, phrases: list[str]) -> bool:
    # punctuation becomes a space, except the . or , inside numbers like 2,17,000
    t = " " + re.sub(r"(?<!\d)[.,]|[.,](?!\d)", " ", norm(text)) + " "
    t = re.sub(r"\s+", " ", t)
    return any((" " + p + " ") in t for p in phrases)


# ---------- simple intents ----------

_YES = ["yes", "yeah", "yep", "yup", "sure", "okay", "ok", "haan", "han", "ha", "hanji", "correct",
        "right", "confirm", "confirmed", "proceed", "agreed", "definitely", "absolutely",
        "accha", "achha", "theek hai", "thik hai", "go ahead", "sounds good", "do it",
        "that works", "save it", "looks good", "save the plan", "that's right", "thats right",
        "i approve", "approved", "that captures it", "captures it"]
_NO = ["no", "nope", "nahi", "nahin", "na", "not really", "don't save", "dont save", "do not save"]
_DONT_KNOW = ["don't know", "dont know", "do not know", "not sure", "no idea", "pata nahi",
              "maloom nahi", "i'm not sure", "im not sure", "can't say", "cant say", "unsure"]
_NOT_NOW = ["not now", "call later", "talk later", "speak later", "call me later", "later please", "i'm busy", "im busy", "busy right now", "call back", "call me back",
            "abhi nahi", "baad mein", "some other time", "not a good time"]
_REPEAT = ["repeat", "say that again", "come again", "what did you say", "pardon", "once more",
           "dobara", "say again", "can you repeat", "sorry what", "i didn't catch", "i didnt catch"]
_WRONG_NUMBER = ["wrong", "incorrect", "not correct", "galat", "doesn't look right", "doesnt look right",
                 "not right", "mismatch"]
_BYE = ["bye", "goodbye", "that's all", "thats all", "nothing else", "that is all", "end the call",
        "thank you", "thanks", "bas", "dhanyavaad", "shukriya", "no that's all", "all good", "we're done",
        "i'm done", "im done"]
_EXPLAIN = ["why", "how do you know", "explain", "what do you mean", "how did you", "tell me more",
            "details", "how come", "what makes you say", "evidence", "proof"]
_RECAP = ["what's the plan", "whats the plan", "read the plan", "recap", "what did we agree",
          "what have we agreed", "summary", "summarise", "summarize", "read it back", "show the plan"]
_PROMO = ["discount", "offer", "ads", "ad", "advertis", "promotion", "promote", "campaign",
          "sponsor", "coupon", "sale price", "boost"]


def is_yes(text: str) -> bool:
    toks = tokens(text)
    if not toks:
        return False
    if is_no(text):
        return False
    return has_any(text, _YES)


def is_no(text: str) -> bool:
    toks = tokens(text)
    if not toks:
        return False
    if has_any(text, ["no problem", "no worries", "no issue"]):
        return False
    if toks[0] in ("no", "nope", "nahi", "nahin", "na"):
        return True
    return has_any(text, ["not really", "don't save", "dont save", "do not save", "don't want", "dont want"])


def is_dont_know(text: str) -> bool:
    return has_any(text, _DONT_KNOW)


def is_not_now(text: str) -> bool:
    return has_any(text, _NOT_NOW)


def is_repeat(text: str) -> bool:
    return has_any(text, _REPEAT)


def is_wrong_number(text: str) -> bool:
    return has_any(text, _WRONG_NUMBER) and has_any(
        text, ["number", "numbers", "figure", "figures", "data", "that", "this", "orders", "sales", "wrong"])


def is_goodbye(text: str) -> bool:
    return has_any(text, _BYE)


def is_explain(text: str) -> bool:
    return has_any(text, _EXPLAIN)


def is_recap(text: str) -> bool:
    return has_any(text, _RECAP)


def is_promo(text: str) -> bool:
    return has_any(text, _PROMO)


# ---------- topics ----------

SKU_WORDS = {
    "DEMO-SKU-01": ["organizer", "organiser", "bamboo", "organize"],
    "DEMO-SKU-02": ["bedsheet", "bed sheet", "bedsheets", "cotton", "bed-sheet"],
    "DEMO-SKU-03": ["jar", "jars", "kitchen", "storage"],
}


def mentioned_sku(text: str) -> Optional[str]:
    for sku, words in SKU_WORDS.items():
        if has_any(text, words):
            return sku
    return None


def classify_concern(text: str) -> str:
    if has_any(text, ["conversion", "convert", "buying", "not buying", "purchase"]):
        return "conversion"
    if has_any(text, ["visit", "visits", "traffic", "views", "viewers", "sessions", "footfall", "clicks", "impressions"]):
        return "visits"
    if has_any(text, ["revenue", "gmv", "income", "earning", "earnings", "paise", "money", "turnover"]):
        return "revenue"
    if has_any(text, ["order", "orders", "sales", "sale", "bikri", "selling", "sell", "dropped", "down", "kam", "low"]):
        return "orders"
    return "unclear"


# ---------- slots ----------

def extract_days(text: str) -> Optional[int]:
    t = norm(text)
    if has_any(t, ["tomorrow", "kal"]):
        return 1
    m = re.search(r"(\d+|[a-z]+)\s*(days?|din|dino|weeks?|hafta|hafte|haftey)\b", t)
    if m:
        qty_raw, unit = m.group(1), m.group(2)
        qty = int(qty_raw) if qty_raw.isdigit() else _WORD_NUM.get(qty_raw)
        if qty is not None:
            return qty * _UNIT_DAYS[unit]
    if has_any(t, ["this week", "next week", "within a week", "end of the week", "is hafte"]):
        return 7
    return None


def extract_amount(text: str, expect_amount: bool = False) -> Optional[float]:
    t = norm(text)
    m = re.search(r"(?:₹|rs\.?|rupees?|inr)\s*(\d[\d,]*(?:\.\d+)?)", t)
    if not m:
        m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:₹|rs\b|rupees?|inr|rupaye)", t)
    if not m and expect_amount:
        # bare number, but not one that is clearly a day/week count
        for cand in re.finditer(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?![\w%])", t):
            tail = t[cand.end():cand.end() + 8].strip()
            if tail.startswith(("day", "din", "week", "hafta", "hafte", "%", "percent")):
                continue
            m = cand
            break
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return val if val > 0 else None


def extract_price_policy(text: str) -> Optional[str]:
    """manual_only: may review, but no automatic change. no_cut: no reduction at all."""
    t = norm(text)
    automatic = has_any(t, ["automatic", "automatically", "on its own", "without asking",
                            "without my approval", "without my permission", "without telling me",
                            "bina poochhe", "apne aap"])
    flat = re.sub(r"[.,]", " ", t)
    neg_reduce = bool(re.search(
        r"\b(no|not|dont|don't|do not|cannot|can't|cant|won't|wont|never)\b[\w\s']{0,18}?"
        r"\b(reduc\w*|lower\w*|cut\w*|discount\w*|drop\w*|chang\w*)", flat)) or has_any(
        t, ["keep the price", "keep price", "price stays", "price will stay",
            "kam nahi", "nahi karunga", "nahi kar sakta", "nahi ghatau", "discount nahi", "price nahi"])
    if automatic and (neg_reduce or has_any(t, ["reduce", "change", "lower", "drop", "cut", "price"])):
        return "manual_only"
    if neg_reduce:
        return "no_cut"
    if has_any(t, ["can reduce", "can lower", "can drop", "okay to reduce", "fine to reduce", "happy to reduce",
                   "ready to reduce", "can cut", "can go down", "can go lower", "can test", "go ahead and test",
                   "can review the price", "can review price", "open to", "can go down", "can accept"]):
        return "open"
    return None


def extract_dispatch_cause(text: str) -> Optional[str]:
    t = norm(text)
    table = [
        (["staff", "staffing", "manpower", "labour", "labor", "workers", "employees"], "staffing shortage"),
        (["pickup", "pick up", "pick-up", "courier", "logistics", "carrier"], "pickup / courier delays"),
        (["packing", "packaging", "packer"], "packing capacity"),
        (["inventory mismatch", "stock mismatch", "stock count", "wrong stock"], "stock accuracy"),
    ]
    for words, label in table:
        if has_any(t, words) and has_any(t, ["dispatch", "delay", "delays", "late", "cancel", "cancellation", "jar", "order"]):
            return label
    return None


def extract_restock(text: str, asked: bool) -> tuple[Optional[str], Optional[int]]:
    """Return (status, days). status in soon / none / unknown / None (not answered)."""
    t = norm(text)
    if has_any(t, ["no stock", "don't have stock", "dont have stock", "do not have stock", "can't restock",
                   "cant restock", "cannot restock", "can not restock", "not possible", "unable to restock",
                   "won't be able", "wont be able", "no way to restock", "supplier has", "supplier is out",
                   "stock nahi", "not restocking", "can't get stock", "cannot get stock"]):
        return "none", None
    days = extract_days(t)
    if days is not None and (asked or has_any(t, ["restock", "stock", "replenish", "supply", "arrive", "come"])):
        return "soon", days
    if asked and is_dont_know(t):
        return "unknown", None
    if asked and has_any(t, ["maybe", "not sure", "depends"]):
        return "unknown", None
    if asked and is_yes(t):
        return "soon", 7        # the question was "this week?", so a plain yes means within 7 days
    if asked and is_no(t):
        return "none", None
    return None, None


def extract_removal(text: str) -> set[str]:
    """Plan item keys the seller wants removed ('drop the price one', 'skip the jar')."""
    t = norm(text)
    if not has_any(t, ["remove", "skip", "drop", "without", "leave out", "leave off", "delete",
                       "don't include", "dont include", "do not include", "exclude", "not the", "take out",
                       "hata", "nahi chahiye"]):
        return set()
    out: set[str] = set()
    sku = mentioned_sku(t)
    if has_any(t, ["price", "pricing", "margin"]):
        out |= {"price_review", "price_test"}
    if has_any(t, ["return", "returns"]):
        out |= {"returns_review"}
    if sku == "DEMO-SKU-01" or has_any(t, ["restock", "replenish"]):
        out |= {"restock"}
    if sku == "DEMO-SKU-02" and not out:
        out |= {"returns_review", "price_review", "price_test"}
    if sku == "DEMO-SKU-03" or has_any(t, ["dispatch", "cancellation", "cancellations", "fulfilment", "fulfillment"]):
        out |= {"dispatch_fix"}
    if has_any(t, ["traffic", "visits", "visit", "visibility"]):
        out |= {"traffic_check"}
    return out
