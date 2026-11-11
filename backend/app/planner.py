"""Turns drivers + what the seller told us into DRAFT action items.

Branches (this is where the seller's answers change the recommendation):
  restock_status : soon / later / none / unknown
  price_policy   : manual_only / no_cut / open / unknown   (+ optional margin_floor)
Nothing here touches a live account. Items are drafts until the seller consents.
"""
from datetime import date, timedelta
from typing import Optional

from .models import ActionItem, Driver
from .analytics import format_inr


def short_name(name: str) -> str:
    """'Bamboo Home Organizer Set' -> 'organizer'. Only used for speech; the UI shows full names."""
    words = [w for w in name.split() if w.lower() not in ("set", "pack", "combo", "kit")]
    return (words[-1] if words else name).lower()


def _due(days: Optional[int]) -> Optional[str]:
    if days is None:
        return None
    return (date.today() + timedelta(days=days)).isoformat()


def build_candidate_actions(data: dict, drivers: list[Driver], facts: dict) -> list[ActionItem]:
    ids = {d.driver_id: d for d in drivers}
    skus = {s["sku_id"]: s for s in data["skus"]}
    items: list[ActionItem] = []

    # ----- availability -----
    for did, d in ids.items():
        if not did.startswith("stockout:"):
            continue
        name = skus[d.sku_id]["name"]
        status = facts.get("restock_status")
        days = facts.get("restock_days")
        if status == "soon" and days is not None:
            items.append(ActionItem(
                key="restock", kind="inventory", consequential=True,
                title=f"Replenish {name}",
                detail=f"Seller restocks within about {days} days. Check availability and orders again after it is live.",
                spoken=f"restock the {short_name(name)} in {days} days",
                owner="Seller", timeframe=f"Within {days} days", due_date=_due(days),
                success_metric=f"Back in stock; stockout days at 0 next period; compare orders with the {skus[d.sku_id]['orders_current']} in the last 30 days.",
                rationale=d.observed_facts[0],
            ))
        elif status == "none":
            items.append(ActionItem(
                key="restock", kind="investigation",
                title=f"Plan around the {name} stockout",
                detail="No restock is possible right now. Keep in-stock products healthy meanwhile and set a restock date as soon as one exists.",
                spoken=f"plan around the {short_name(name)} stockout",
                owner="Seller", timeframe="Set a restock date within 7 days", due_date=_due(7),
                success_metric="A restock date is decided and logged.",
                rationale=d.observed_facts[0],
            ))
        else:  # later / unknown
            items.append(ActionItem(
                key="restock", kind="investigation",
                title=f"Confirm a restock date for {name}",
                detail="Restock timing is not known yet. Get a date from the supplier or warehouse before planning anything else around this product.",
                spoken=f"confirm the {short_name(name)} restock date",
                owner="Seller", timeframe="This week", due_date=_due(7),
                success_metric="Restock date confirmed and shared at the next check-in.",
                rationale=d.observed_facts[0],
            ))

    # ----- price + returns -----
    for did, d in ids.items():
        if not did.startswith("price_returns:"):
            continue
        s = skus[d.sku_id]
        name, price, bench = s["name"], s["selling_price"], s["benchmark_price"]
        policy = facts.get("price_policy")
        floor = facts.get("margin_floor")
        items.append(ActionItem(
            key="returns_review", kind="listing",
            title=f"Review {name} return reasons",
            detail="Find the leading return reason first. A listing or quality fix may matter more than price.",
            spoken=f"review {short_name(name)} return reasons",
            owner="Seller", timeframe="This week", due_date=_due(7),
            success_metric=f"Leading return reason identified; return rate moves from {s['return_rate_pct']:.0f}% toward the {data['targets']['category_return_rate_pct']:.0f}% demo baseline.",
            rationale=" | ".join(d.observed_facts[:2]),
        ))
        room = floor is not None and price is not None and floor < price
        if policy in ("no_cut",):
            pass  # seller said no price reduction: no price item at all
        elif room and policy == "open":
            test_price = max(floor, bench)
            items.append(ActionItem(
                key="price_test", kind="price", consequential=True,
                title=f"Draft a small price test on {name}: {format_inr(test_price)}",
                detail=(f"Stays at or above your minimum of {format_inr(floor)}. Draft only: nothing is changed "
                        "until you approve it, and it can be reverted. This is a test, not a promise of more orders."),
                spoken=f"draft a {short_name(name)} price test at {format_inr(test_price)}, only with your approval",
                owner="Seller (approval needed)", timeframe="After the returns review", due_date=_due(10),
                success_metric="Compare orders and returns for the test period against the current price.",
                rationale=d.observed_facts[0],
            ))
        else:
            # manual_only (seller will decide), unknown margin, or no room under the floor
            if policy == "manual_only" and floor is not None and not room:
                why = f"Your minimum of {format_inr(floor)} leaves no room below the current {format_inr(price)}."
            elif floor is not None and not room:
                why = f"Your minimum of {format_inr(floor)} leaves no room below the current {format_inr(price)}."
            else:
                why = "Margin floor is not confirmed, so no price change is drafted."
            items.append(ActionItem(
                key="price_review", kind="price", consequential=True,
                title=f"Review {name} price against your margin (no automatic change)",
                detail=f"{why} You decide any price move yourself; SellerPulse will not change it.",
                spoken=f"review {short_name(name)} price against your margin, with no automatic change",
                owner="Seller", timeframe="After the returns review", due_date=_due(10),
                success_metric="A margin-based decision on whether any price test is worth running.",
                rationale=d.observed_facts[0],
            ))

    # ----- fulfilment -----
    for did, d in ids.items():
        if not did.startswith("fulfilment:"):
            continue
        s = skus[d.sku_id]
        cause = facts.get("dispatch_cause")
        extra = f" Seller mentioned: {cause}." if cause else ""
        items.append(ActionItem(
            key="dispatch_fix", kind="fulfilment",
            title=f"Investigate late dispatch and cancellations on {s['name']}",
            detail="Find out what is causing the delays (staffing, pickup timing or stock accuracy) before spending on any promotion." + extra,
            spoken=f"look into {short_name(s['name'])} dispatch delays and cancellations",
            owner="Seller", timeframe="Within 7 days", due_date=_due(7),
            success_metric=(f"Late dispatch from {s['late_dispatch_rate_pct']:.0f}% toward the "
                            f"{data['targets']['late_dispatch_rate_pct']:.0f}% demo target; cancellations from "
                            f"{s['cancellation_rate_pct']:.0f}% toward {data['targets']['cancellation_rate_pct']:.0f}%."),
            rationale=" | ".join(d.observed_facts[:2]),
        ))

    # ----- traffic -----
    if "traffic" in ids:
        d = ids["traffic"]
        items.append(ActionItem(
            key="traffic_check", kind="investigation",
            title="Check why product-page visits dipped",
            detail="Look at listing visibility and any promotion changes in the period. No ad spend is proposed until the cause is known.",
            spoken="check why visits dipped",
            owner="Seller with SellerPulse follow-up", timeframe="Next check-in", due_date=_due(7),
            success_metric="Visits compared again at the next 30-day check; cause noted if found.",
            rationale=d.observed_facts[0],
        ))

    return items
