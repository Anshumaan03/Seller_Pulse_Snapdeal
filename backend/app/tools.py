"""The agent's tool layer. Each function is plain Python with typed output.

The dialogue controller (or an LLM) decides WHICH tool to call; the numbers
always come from analytics.py.
"""
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import analytics, db
from .models import (
    SellerProfile, PeriodComparison, SkuDiagnostic, Driver,
    ActionPriority, ActionItem, ActionPlan, CallSummary,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_LABEL = "Synthetic demo data - not Snapdeal seller data"


class ToolError(Exception):
    pass


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_data(seller_id: Optional[str] = None) -> dict:
    path = os.environ.get("SELLERPULSE_DATA", str(ROOT / "data" / "demo_seller.json"))
    data = _load(path)
    if seller_id is not None and data["seller"]["seller_id"] != seller_id:
        raise ToolError(f"Unknown seller_id {seller_id!r}. This demo only has {data['seller']['seller_id']}.")
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# 1
def get_seller_profile(seller_id: str) -> SellerProfile:
    d = load_data(seller_id)
    s = d["seller"]
    return SellerProfile(
        seller_id=s["seller_id"], name=s["name"], category=s["category"], region=s["region"],
        data_label=DATA_LABEL,
        current_window=d["windows"]["current"]["label"],
        previous_window=d["windows"]["previous"]["label"],
    )


# 2
def get_period_comparison(seller_id: str, current_window: str = "current",
                          previous_window: str = "previous") -> PeriodComparison:
    # The seed file holds exactly one pair of windows. Anything else is rejected
    # rather than silently answered with the wrong period.
    if (current_window, previous_window) != ("current", "previous"):
        raise ToolError("Only the current vs previous 30-day windows exist in the demo data.")
    d = load_data(seller_id)
    return analytics.period_comparison(seller_id, d["account"])


# 3
def get_sku_diagnostics(seller_id: str) -> list[SkuDiagnostic]:
    return analytics.sku_diagnostics(load_data(seller_id))


# 4
def identify_sales_drivers(seller_id: str) -> list[Driver]:
    return analytics.identify_drivers(load_data(seller_id))


# 5
_EFFORT = {"inventory": "Medium", "price": "Low", "fulfilment": "Medium",
           "listing": "Low", "investigation": "Low"}
_SCORE = {"High": 3, "Medium": 2, "Low": 1}


def estimate_action_priority(action: ActionItem, evidence: Optional[Driver],
                             seller_constraints: Optional[dict] = None) -> ActionPriority:
    """Transparent score: impact*3 + urgency*2 + confidence*2 - effort.
    No revenue uplift is estimated anywhere."""
    seller_constraints = seller_constraints or {}
    effort = _EFFORT.get(action.kind, "Medium")
    if evidence is None:
        impact = confidence = urgency = "Low"
        why = "No supporting driver found, so it is ranked low."
    else:
        impact, confidence, urgency = evidence.impact, evidence.confidence, evidence.urgency
        why = (f"Impact {impact} (share of the order drop), confidence {confidence}, "
               f"urgency {urgency}, effort {effort}.")
    score = _SCORE[impact] * 3 + _SCORE[urgency] * 2 + _SCORE[confidence] * 2 - _SCORE[effort]

    blocked = None
    if action.kind == "price" and seller_constraints.get("price_policy") == "no_cut":
        blocked = "Seller does not want a price reduction."
    if action.kind == "price" and seller_constraints.get("margin_floor") is None \
            and seller_constraints.get("price_policy") != "manual_only":
        blocked = "Margin floor unknown: confirm it before any price change."
    return ActionPriority(
        action=action.title, impact=impact, confidence=confidence, urgency=urgency, effort=effort,
        score=float(score), rank_reason=why, blocked_reason=blocked,
    )


# 6
def create_action_plan(seller_id: str, approved_actions: list[ActionItem],
                       consent_confirmed: bool = False) -> ActionPlan:
    """Save the plan. Refuses unless the seller's consent was captured by the caller."""
    load_data(seller_id)
    if not consent_confirmed:
        raise ToolError("Seller consent is required before an action plan is saved.")
    if not approved_actions:
        raise ToolError("No actions to save.")
    ts = _now()
    stored = []
    for a in approved_actions:
        a = a.model_copy(update={"status": "Draft (simulated)", "consent": "Approved by seller",
                                 "simulated": True})
        stored.append(a.model_dump())
    db.save_items(seller_id, stored, ts)
    return ActionPlan(seller_id=seller_id, items=[ActionItem(**x) for x in stored], created_at=ts)


# 7
def get_action_plan(seller_id: str) -> ActionPlan:
    load_data(seller_id)
    items, ts = db.load_items(seller_id)
    return ActionPlan(seller_id=seller_id, items=[ActionItem(**x) for x in items], created_at=ts)


# 8
def log_call_summary(seller_id: str, summary: str, decisions: list[str], follow_up: str) -> CallSummary:
    load_data(seller_id)
    ts = _now()
    cs = CallSummary(seller_id=seller_id, summary=summary, decisions=decisions,
                     follow_up=follow_up, created_at=ts)
    db.save_summary(seller_id, cs.model_dump(), ts)
    return cs


def get_call_summaries(seller_id: str) -> list[CallSummary]:
    load_data(seller_id)
    return [CallSummary(**x) for x in db.load_summaries(seller_id)]


def reset_demo(seller_id: str) -> None:
    load_data(seller_id)
    db.reset_seller(seller_id)
