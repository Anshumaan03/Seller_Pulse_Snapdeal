"""Typed shapes for tool inputs/outputs. Kept small on purpose."""
from typing import Optional, Literal
from pydantic import BaseModel, Field


class SellerProfile(BaseModel):
    seller_id: str
    name: str
    category: str
    region: str
    data_label: str
    current_window: str
    previous_window: str


class WindowTotals(BaseModel):
    gmv: float
    orders: int
    sessions: int
    aov: Optional[float]
    conversion_pct: Optional[float]


class PeriodComparison(BaseModel):
    seller_id: str
    previous: WindowTotals
    current: WindowTotals
    gmv_change_pct: Optional[float]
    orders_change_pct: Optional[float]
    sessions_change_pct: Optional[float]
    aov_change_pct: Optional[float]
    conversion_change_pp: Optional[float]  # percentage points, not percent
    # Orders lost split into a traffic part and a conversion part.
    # Pure arithmetic on the two windows - it is NOT a causal claim.
    orders_lost_total: int
    orders_lost_from_traffic: Optional[float]
    orders_lost_from_conversion: Optional[float]


class SkuDiagnostic(BaseModel):
    sku_id: str
    name: str
    orders_previous: int
    orders_current: int
    orders_change: int
    orders_change_pct: Optional[float]
    share_of_total_order_drop_pct: Optional[float]
    stockout_days: Optional[int]
    stock_available: Optional[int]
    selling_price: Optional[float]
    benchmark_price: Optional[float]
    price_gap_pct: Optional[float]
    return_rate_pct: Optional[float]
    return_gap_pp: Optional[float]
    late_dispatch_rate_pct: Optional[float]
    late_dispatch_gap_pp: Optional[float]
    cancellation_rate_pct: Optional[float]
    cancellation_gap_pp: Optional[float]


class Driver(BaseModel):
    driver_id: str
    title: str
    sku_id: Optional[str] = None
    observed_facts: list[str]          # straight from the data
    likely_explanation: str            # hypothesis, worded as such
    to_verify: list[str]               # questions / missing data
    orders_linked: Optional[int] = None  # orders lost on the linked SKU/metric
    confidence: Literal["High", "Medium", "Low"]
    impact: Literal["High", "Medium", "Low"]
    urgency: Literal["High", "Medium", "Low"]
    missing_data: list[str] = Field(default_factory=list)


class ActionPriority(BaseModel):
    action: str
    impact: Literal["High", "Medium", "Low"]
    confidence: Literal["High", "Medium", "Low"]
    urgency: Literal["High", "Medium", "Low"]
    effort: Literal["High", "Medium", "Low"]
    score: float
    rank_reason: str
    blocked_reason: Optional[str] = None


class ActionItem(BaseModel):
    key: str                       # stable id, e.g. "restock_organizer"
    title: str
    detail: str
    kind: Literal["inventory", "price", "fulfilment", "listing", "investigation"]
    owner: str
    timeframe: str
    due_date: Optional[str] = None
    success_metric: str
    spoken: str = ""               # short phrase the agent says aloud
    priority: Literal["High", "Medium", "Low"] = "Medium"
    rationale: str = ""
    consequential: bool = False    # price/discount/ad/inventory changes
    status: str = "Draft (simulated)"
    consent: str = "Approved by seller"
    simulated: bool = True


class ActionPlan(BaseModel):
    seller_id: str
    items: list[ActionItem]
    created_at: Optional[str] = None
    note: str = "Simulated draft plan. Nothing here was applied to a live Snapdeal account."


class CallSummary(BaseModel):
    seller_id: str
    summary: str
    decisions: list[str]
    follow_up: str
    created_at: Optional[str] = None
