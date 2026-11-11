"""Optional LLM layer. Off unless LLM_API_KEY and LLM_MODEL are set.

Two narrow jobs, both behind guards:
  1. rewrite()  - make the controller's draft sound more natural. The result is only used
                  if it contains no number or product name that was not in the draft.
  2. classify() - label an utterance the rules could not understand.
If anything fails (no key, network, quota, guard) the original draft is used, so a bad
LLM response can never change a metric or skip the consent step.

Uses the OpenAI-compatible chat-completions protocol, which Gemini, OpenAI and
others expose, via plain httpx so there is no extra SDK.
"""
import os
import re
from typing import Optional, Callable

import httpx

from .prompts import KAM_SYSTEM_PROMPT, REWRITE_INSTRUCTION, CLASSIFY_INSTRUCTION  # noqa: F401  (re-exported for check_llm.py)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
LABELS = {"yes", "no", "dont_know", "not_now", "repeat", "other"}

# Test seam: replace with a fake (messages -> text) in unit tests.
_transport: Optional[Callable[[list[dict]], str]] = None


def enabled() -> bool:
    return _transport is not None or bool(os.environ.get("LLM_API_KEY") and os.environ.get("LLM_MODEL"))


def info() -> dict:
    return {
        "enabled": enabled(),
        "model": os.environ.get("LLM_MODEL") if enabled() else None,
        "base_url": os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL) if enabled() else None,
    }


def _chat(messages: list[dict]) -> str:
    if _transport is not None:
        return _transport(messages)
    base = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
        json={"model": os.environ["LLM_MODEL"], "messages": messages, "temperature": 0.4, "max_tokens": 220},
        timeout=8.0,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(text)}


def _caps_words(text: str) -> set[str]:
    return {w for w in re.findall(r"\b[A-Z][a-z]{3,}\b", text)}


def guard_ok(draft: str, rewritten: str) -> bool:
    """Reject a rewrite that adds numbers/names, drops numbers, or balloons in length."""
    if not rewritten or len(rewritten) > max(len(draft) * 1.5, 120):
        return False
    if _numbers(rewritten) != _numbers(draft):
        return False
    if not _caps_words(rewritten) <= (_caps_words(draft) | {"Hello", "Okay", "Right", "Sure", "Thanks", "Good", "Great"}):
        return False
    # a rewrite must not claim a change was made
    if re.search(r"\b(i've|i have)\s+(changed|updated|applied|reduced|lowered)\b", rewritten.lower()):
        return False
    # questions must stay questions
    if draft.rstrip().endswith("?") and not rewritten.rstrip().endswith("?"):
        return False
    return True


def rewrite(draft: str) -> str:
    if not enabled():
        return draft
    try:
        out = _chat([
            {"role": "system", "content": KAM_SYSTEM_PROMPT},
            {"role": "user", "content": f"{REWRITE_INSTRUCTION}\n\nDRAFT:\n{draft}"},
        ])
    except Exception:
        return draft
    return out if guard_ok(draft, out) else draft


def classify(text: str) -> str:
    if not enabled():
        return "other"
    try:
        out = _chat([
            {"role": "system", "content": CLASSIFY_INSTRUCTION},
            {"role": "user", "content": text},
        ]).strip().lower()
    except Exception:
        return "other"
    return out if out in LABELS else "other"
