import json
import pytest
from app import analytics as a, tools

SID = "DEMO-1042"


def test_pct_change_formula_and_guards():
    assert a.pct_change(70, 100) == pytest.approx(-30.0)
    assert a.pct_change(150, 100) == pytest.approx(50.0)
    assert a.pct_change(5, 0) is None        # no previous value
    assert a.pct_change(None, 10) is None
    assert a.pct_change(0, 10) == pytest.approx(-100.0)


def test_aov_and_conversion_guard_zero():
    assert a.aov(310000, 500) == 620
    assert a.aov(0, 0) is None
    assert a.conversion_pct(500, 12500) == pytest.approx(4.0)
    assert a.conversion_pct(5, 0) is None


def test_period_comparison_matches_brief():
    pc = tools.get_period_comparison(SID)
    assert pc.gmv_change_pct == pytest.approx(-30.0)
    assert pc.orders_change_pct == pytest.approx(-30.0)
    assert pc.sessions_change_pct == pytest.approx(-10.0)
    assert pc.previous.aov == pc.current.aov == 620
    assert pc.previous.conversion_pct == pytest.approx(4.0)
    assert pc.current.conversion_pct == pytest.approx(3.1111, abs=1e-3)
    assert pc.conversion_change_pp == pytest.approx(-0.8889, abs=1e-3)


def test_gmv_reconciles_with_orders_times_aov(demo_data):
    for w in ("previous", "current"):
        b = demo_data["account"][w]
        assert b["orders"] * (b["gmv"] / b["orders"]) == pytest.approx(b["gmv"])
    pc = tools.get_period_comparison(SID)
    assert pc.previous.orders * pc.previous.aov == pytest.approx(pc.previous.gmv)
    assert pc.current.orders * pc.current.aov == pytest.approx(pc.current.gmv)


def test_traffic_and_conversion_split_adds_up():
    pc = tools.get_period_comparison(SID)
    assert pc.orders_lost_from_traffic == pytest.approx(50)
    assert pc.orders_lost_from_conversion == pytest.approx(100)
    assert pc.orders_lost_from_traffic + pc.orders_lost_from_conversion == pytest.approx(pc.orders_lost_total)


def test_seed_data_reconciles(demo_data):
    assert a.reconcile(demo_data) == []


def test_reconcile_flags_bad_data(demo_data):
    demo_data["skus"][0]["orders_current"] += 5
    problems = a.reconcile(demo_data)
    assert problems and "current" in problems[0]


def test_sku_decline_ranking_and_shares():
    diag = tools.get_sku_diagnostics(SID)
    assert [d.orders_change for d in diag] == [-72, -45, -23, -10]
    assert diag[0].name == "Bamboo Home Organizer Set"
    assert sum(d.share_of_total_order_drop_pct for d in diag) == pytest.approx(100)


def test_sku_signals():
    diag = {d.sku_id: d for d in tools.get_sku_diagnostics(SID)}
    bamboo, bed, jar, other = (diag[k] for k in ("DEMO-SKU-01", "DEMO-SKU-02", "DEMO-SKU-03", "DEMO-SKU-04"))
    assert bamboo.stockout_days == 9 and bamboo.orders_change_pct == pytest.approx(-51.43, abs=0.01)
    assert bed.price_gap_pct == pytest.approx(8.44, abs=0.01)
    assert bed.return_gap_pp == pytest.approx(7.0)
    assert jar.late_dispatch_gap_pp == pytest.approx(12.0)
    assert jar.cancellation_gap_pp == pytest.approx(5.0)
    # missing fields stay None instead of being invented
    assert other.price_gap_pct is None and other.return_gap_pp is None and other.stockout_days is None


def test_zero_previous_orders_does_not_crash(demo_data, tmp_path, monkeypatch):
    demo_data["skus"][3]["orders_previous"] = 0
    demo_data["account"]["previous"]["orders"] -= 165
    p = tmp_path / "d.json"
    p.write_text(json.dumps(demo_data))
    monkeypatch.setenv("SELLERPULSE_DATA", str(p))
    other = next(d for d in tools.get_sku_diagnostics(SID) if d.sku_id == "DEMO-SKU-04")
    assert other.orders_change_pct is None


def test_drivers_ranked_and_evidence_backed():
    drivers = tools.identify_sales_drivers(SID)
    ids = [d.driver_id for d in drivers]
    assert ids[0] == "stockout:DEMO-SKU-01"
    assert set(ids) == {"stockout:DEMO-SKU-01", "traffic", "price_returns:DEMO-SKU-02", "fulfilment:DEMO-SKU-03"}
    # the SKU with no verified signal gets no driver
    assert not any("SKU-04" in i for i in ids)
    bed = next(d for d in drivers if d.driver_id.startswith("price_returns"))
    assert bed.confidence == "Low"                    # price gap is a test opportunity, not proof
    assert "not proof" in bed.likely_explanation
    assert all(d.missing_data for d in drivers)       # every driver states what we do not know


def test_drivers_follow_the_data_not_a_script(demo_data, tmp_path, monkeypatch):
    demo_data["skus"][0]["stockout_days_current"] = 0      # remove the stockout
    demo_data["skus"][0]["stock_available"] = 12
    p = tmp_path / "d.json"
    p.write_text(json.dumps(demo_data))
    monkeypatch.setenv("SELLERPULSE_DATA", str(p))
    assert not any(d.driver_id.startswith("stockout") for d in tools.identify_sales_drivers(SID))


def test_priority_has_no_uplift_number_and_blocks_price_without_margin():
    from app.planner import build_candidate_actions
    drivers = tools.identify_sales_drivers(SID)
    items = build_candidate_actions(tools.load_data(), drivers, {"price_policy": "unknown"})
    price = next(i for i in items if i.kind == "price")
    ev = next(d for d in drivers if d.driver_id.startswith("price_returns"))
    pr = tools.estimate_action_priority(price, ev, {"price_policy": "unknown", "margin_floor": None})
    assert pr.blocked_reason and "Margin floor" in pr.blocked_reason
    assert "%" not in pr.rank_reason and "uplift" not in pr.rank_reason.lower()


def test_unknown_seller_and_window_rejected():
    with pytest.raises(tools.ToolError):
        tools.get_seller_profile("NOPE")
    with pytest.raises(tools.ToolError):
        tools.get_period_comparison(SID, "last_7_days", "previous")


def test_formatting_helpers():
    assert a.format_inr(217000) == "₹2,17,000"
    assert a.format_inr(310000) == "₹3,10,000"
    assert a.format_inr(999) == "₹999"
    assert a.format_inr(1234567) == "₹12,34,567"
    assert a.short_pct(30.0, 0) == "30"
    assert a.short_pct(3.111) == "3.1"
    assert a.short_pct(4.0) == "4"
