"""Pure, deterministic business logic. No I/O, no LLM.

Everything the agent says about the seller's numbers comes from here.
"""
from typing import Optional

from .models import (
    PeriodComparison, WindowTotals, SkuDiagnostic, Driver,
)


# ---------- small helpers (zero / missing safe) ----------

def pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """(current - previous) / previous * 100. None when it cannot be computed."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous * 100


def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def aov(gmv: float, orders: int) -> Optional[float]:
    return safe_div(gmv, orders)


def conversion_pct(orders: int, sessions: int) -> Optional[float]:
    r = safe_div(orders, sessions)
    return None if r is None else r * 100


def gap(value: Optional[float], baseline: Optional[float]) -> Optional[float]:
    """value - baseline (used for percentage-point gaps). None if either is missing."""
    if value is None or baseline is None:
        return None
    return value - baseline


def _totals(block: dict) -> WindowTotals:
    return WindowTotals(
        gmv=block["gmv"],
        orders=block["orders"],
        sessions=block["sessions"],
        aov=aov(block["gmv"], block["orders"]),
        conversion_pct=conversion_pct(block["orders"], block["sessions"]),
    )


# ---------- account level ----------

def period_comparison(seller_id: str, account: dict) -> PeriodComparison:
    prev, cur = _totals(account["previous"]), _totals(account["current"])

    conv_change_pp = gap(cur.conversion_pct, prev.conversion_pct)

    # Orders lost, split into "fewer visits" and "worse conversion".
    #   traffic part    = (sessions_now - sessions_before) * old conversion rate
    #   conversion part = sessions_now * (new conversion - old conversion)
    # The two parts add up exactly to the order change. This is arithmetic on the
    # two windows. It says nothing about WHY traffic or conversion moved.
    traffic_part = conv_part = None
    if prev.conversion_pct is not None and cur.conversion_pct is not None:
        old_cr = prev.conversion_pct / 100
        new_cr = cur.conversion_pct / 100
        traffic_part = (cur.sessions - prev.sessions) * old_cr
        conv_part = cur.sessions * (new_cr - old_cr)

    return PeriodComparison(
        seller_id=seller_id,
        previous=prev,
        current=cur,
        gmv_change_pct=pct_change(cur.gmv, prev.gmv),
        orders_change_pct=pct_change(cur.orders, prev.orders),
        sessions_change_pct=pct_change(cur.sessions, prev.sessions),
        aov_change_pct=pct_change(cur.aov, prev.aov),
        conversion_change_pp=conv_change_pp,
        orders_lost_total=prev.orders - cur.orders,
        orders_lost_from_traffic=None if traffic_part is None else -traffic_part,
        orders_lost_from_conversion=None if conv_part is None else -conv_part,
    )


def reconcile(data: dict) -> list[str]:
    """Return a list of problems found in the seed data (empty list = it reconciles)."""
    problems = []
    acc = data["account"]
    for window, key in (("previous", "orders_previous"), ("current", "orders_current")):
        sku_total = sum(s[key] for s in data["skus"])
        if sku_total != acc[window]["orders"]:
            problems.append(
                f"SKU orders ({window}) sum to {sku_total} but account orders are {acc[window]['orders']}"
            )
    return problems


# ---------- SKU level ----------

def sku_diagnostics(data: dict) -> list[SkuDiagnostic]:
    acc = data["account"]
    total_drop = acc["previous"]["orders"] - acc["current"]["orders"]
    targets = data["targets"]
    out = []
    for s in data["skus"]:
        change = s["orders_current"] - s["orders_previous"]
        drop = -change
        share = None
        if total_drop > 0:
            share = max(drop, 0) / total_drop * 100
        price_gap = None
        if s.get("selling_price") is not None and s.get("benchmark_price"):
            price_gap = pct_change(s["selling_price"], s["benchmark_price"])
        out.append(SkuDiagnostic(
            sku_id=s["sku_id"],
            name=s["name"],
            orders_previous=s["orders_previous"],
            orders_current=s["orders_current"],
            orders_change=change,
            orders_change_pct=pct_change(s["orders_current"], s["orders_previous"]),
            share_of_total_order_drop_pct=share,
            stockout_days=s.get("stockout_days_current"),
            stock_available=s.get("stock_available"),
            selling_price=s.get("selling_price"),
            benchmark_price=s.get("benchmark_price"),
            price_gap_pct=price_gap,
            return_rate_pct=s.get("return_rate_pct"),
            return_gap_pp=gap(s.get("return_rate_pct"), targets.get("category_return_rate_pct")),
            late_dispatch_rate_pct=s.get("late_dispatch_rate_pct"),
            late_dispatch_gap_pp=gap(s.get("late_dispatch_rate_pct"), targets.get("late_dispatch_rate_pct")),
            cancellation_rate_pct=s.get("cancellation_rate_pct"),
            cancellation_gap_pp=gap(s.get("cancellation_rate_pct"), targets.get("cancellation_rate_pct")),
        ))
    # biggest absolute order decline first
    out.sort(key=lambda d: d.orders_change)
    return out


# ---------- drivers ----------

_LEVEL_SCORE = {"High": 3, "Medium": 2, "Low": 1}


def _impact_from_share(share_pct: Optional[float]) -> str:
    # share of the account's total order drop that sits on this item
    if share_pct is None:
        return "Low"
    if share_pct >= 25:
        return "High"
    if share_pct >= 10:
        return "Medium"
    return "Low"


def identify_drivers(data: dict) -> list[Driver]:
    """Rank likely contributors to the sales dip.

    Observed facts come straight from the numbers. 'likely_explanation' is always a
    hypothesis. Ranking = impact*3 + urgency*2 + confidence*2 (effort is applied later
    in estimate_action_priority because it depends on the action chosen).
    """
    pc = period_comparison(data["seller"]["seller_id"], data["account"])
    skus = {d.sku_id: d for d in sku_diagnostics(data)}
    targets = data["targets"]
    drivers: list[Driver] = []

    # 1) availability
    for d in skus.values():
        if d.stockout_days and d.stockout_days > 0:
            lost = -d.orders_change
            still_out = d.stock_available == 0
            drivers.append(Driver(
                driver_id=f"stockout:{d.sku_id}",
                title=f"{d.name} was out of stock",
                sku_id=d.sku_id,
                observed_facts=[
                    f"Out of stock for {d.stockout_days} of the last 30 days"
                    + (" and still at zero stock" if still_out else ""),
                    f"Orders fell from {d.orders_previous} to {d.orders_current} "
                    f"({d.orders_change_pct:.0f}%)",
                    f"That is {lost} of the {pc.orders_lost_total} orders lost "
                    f"({d.share_of_total_order_drop_pct:.0f}% of the drop)",
                ],
                likely_explanation=(
                    "Missing availability probably cut this product's orders. The data shows the two "
                    "moving together; it does not prove the stockout was the only reason."
                ),
                to_verify=["When can fresh stock arrive?"],
                orders_linked=lost,
                confidence="High" if d.stockout_days >= 5 else "Medium",
                impact=_impact_from_share(d.share_of_total_order_drop_pct),
                urgency="High" if still_out else "Medium",
                missing_data=["Daily orders during the stockout window"],
            ))

    # 2) traffic (investigate, do not assume a cause)
    if pc.sessions_change_pct is not None and pc.sessions_change_pct < -2:
        lost_t = pc.orders_lost_from_traffic
        share_t = None
        if lost_t is not None and pc.orders_lost_total > 0:
            share_t = lost_t / pc.orders_lost_total * 100
        drivers.append(Driver(
            driver_id="traffic",
            title="Fewer product-page visits",
            observed_facts=[
                f"Sessions fell from {pc.previous.sessions:,} to {pc.current.sessions:,} "
                f"({pc.sessions_change_pct:.0f}%)",
                f"At the old conversion rate that is roughly {lost_t:.0f} fewer orders "
                f"({share_t:.0f}% of the drop)" if lost_t is not None and share_t is not None
                else "Order effect of lower traffic could not be computed",
                "The rest of the drop is lower conversion "
                + (f"({pc.previous.conversion_pct:.2f}% to {pc.current.conversion_pct:.2f}%)"
                   if pc.previous.conversion_pct is not None and pc.current.conversion_pct is not None else ""),
            ],
            likely_explanation=(
                "Traffic alone does not explain the decline, and the data here cannot say why visits fell."
            ),
            to_verify=["Did listing visibility, search placement or promotions change in this period?"],
            orders_linked=None if lost_t is None else round(lost_t),
            confidence="Medium",
            impact=_impact_from_share(share_t),
            urgency="Medium",
            missing_data=["Impressions / search visibility", "Promotion and ad history", "Category demand"],
        ))

    # 3) price + returns
    for d in skus.values():
        has_price_gap = d.price_gap_pct is not None and d.price_gap_pct > 3
        has_return_gap = d.return_gap_pp is not None and d.return_gap_pp > 3
        if has_price_gap or has_return_gap:
            facts = []
            if has_price_gap:
                facts.append(
                    f"Listed at ₹{d.selling_price:.0f} against a supplied demo benchmark of "
                    f"₹{d.benchmark_price:.0f} ({d.price_gap_pct:.1f}% higher)"
                )
            if has_return_gap:
                facts.append(
                    f"Return rate {d.return_rate_pct:.0f}% against a demo baseline of "
                    f"{targets['category_return_rate_pct']:.0f}%"
                )
            facts.append(
                f"Orders fell from {d.orders_previous} to {d.orders_current} ({d.orders_change_pct:.0f}%)"
            )
            drivers.append(Driver(
                driver_id=f"price_returns:{d.sku_id}",
                title=f"{d.name}: price above benchmark and higher returns",
                sku_id=d.sku_id,
                observed_facts=facts,
                likely_explanation=(
                    "The price gap is a test opportunity, not proof that price caused the decline. "
                    "Higher returns may point to a listing or product-quality issue; the reason is unknown."
                ),
                to_verify=["What is the seller's minimum acceptable price?", "What is the leading return reason?"],
                orders_linked=-d.orders_change,
                confidence="Low",
                impact=_impact_from_share(d.share_of_total_order_drop_pct),
                urgency="Medium",
                missing_data=["Return reasons", "Seller margin", "Real competitor prices"],
            ))

    # 4) fulfilment
    for d in skus.values():
        late_bad = d.late_dispatch_gap_pp is not None and d.late_dispatch_gap_pp > 3
        cancel_bad = d.cancellation_gap_pp is not None and d.cancellation_gap_pp > 2
        if late_bad or cancel_bad:
            facts = []
            if late_bad:
                facts.append(
                    f"Late dispatch {d.late_dispatch_rate_pct:.0f}% against a mock target of "
                    f"{targets['late_dispatch_rate_pct']:.0f}%"
                )
            if cancel_bad:
                facts.append(
                    f"Cancellations {d.cancellation_rate_pct:.0f}% against a mock target of "
                    f"{targets['cancellation_rate_pct']:.0f}%"
                )
            facts.append(
                f"Orders fell from {d.orders_previous} to {d.orders_current} ({d.orders_change_pct:.0f}%)"
            )
            drivers.append(Driver(
                driver_id=f"fulfilment:{d.sku_id}",
                title=f"{d.name}: late dispatch and cancellations",
                sku_id=d.sku_id,
                observed_facts=facts,
                likely_explanation=(
                    "Fulfilment misses can hurt repeat orders and ratings. The link to this product's "
                    "order decline is a hypothesis; the dataset does not show it directly."
                ),
                to_verify=["What is behind the delays: staffing, pickup timing or stock accuracy?"],
                orders_linked=-d.orders_change,
                confidence="Low",
                impact=_impact_from_share(d.share_of_total_order_drop_pct),
                urgency="Medium",
                missing_data=["Cancellation reasons", "Dispatch timestamps"],
            ))

    drivers.sort(
        key=lambda x: (
            _LEVEL_SCORE[x.impact] * 3 + _LEVEL_SCORE[x.urgency] * 2 + _LEVEL_SCORE[x.confidence] * 2
        ),
        reverse=True,
    )
    return drivers


def driver_score(d: Driver) -> int:
    return _LEVEL_SCORE[d.impact] * 3 + _LEVEL_SCORE[d.urgency] * 2 + _LEVEL_SCORE[d.confidence] * 2


def priority_label(score: float) -> str:
    # max possible = 9 + 6 + 6 - 1 = 20 (effort Low), min = 3 + 2 + 2 - 3 = 4
    if score >= 14:
        return "High"
    if score >= 9:
        return "Medium"
    return "Low"


# ---------- formatting for speech / UI ----------

def format_inr(amount: float) -> str:
    """Indian digit grouping: 217000 -> Rs 2,17,000."""
    n = int(round(amount))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + "₹" + s


def short_pct(x: Optional[float], digits: int = 1) -> str:
    """4.0 -> '4', 3.111 -> '3.1', -30.0 -> '30' (magnitude only; caller adds up/down)."""
    if x is None:
        return "n/a"
    txt = f"{abs(x):.{digits}f}"
    if "." in txt:
        txt = txt.rstrip("0").rstrip(".")
    return txt
