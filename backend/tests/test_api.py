SID = "DEMO-1042"


def test_health_and_config(client):
    assert client.get("/api/health").json()["status"] == "ok"
    cfg = client.get("/api/config").json()
    assert cfg["voice_mode"] == "browser" and cfg["llm"]["enabled"] is False


def test_snapshot(client):
    r = client.get(f"/api/seller/{SID}/snapshot").json()
    assert r["profile"]["name"].startswith("Riya Home")
    assert "Synthetic" in r["profile"]["data_label"]
    assert r["comparison"]["orders_change_pct"] == -30.0
    assert r["reconciliation_problems"] == []


def test_diagnosis(client):
    r = client.get(f"/api/seller/{SID}/diagnosis").json()
    assert r["drivers"][0]["driver_id"].startswith("stockout")
    assert len(r["skus"]) == 4


def test_unknown_seller_404(client):
    assert client.get("/api/seller/NOPE/snapshot").status_code == 404
    assert client.post("/api/call/start", json={"seller_id": "NOPE"}).status_code == 404


ITEM = {
    "key": "restock", "title": "Replenish X", "detail": "d", "kind": "inventory", "owner": "Seller",
    "timeframe": "Within 3 days", "success_metric": "m",
}


def test_action_plan_needs_consent_then_persists_and_resets(client):
    r = client.post(f"/api/seller/{SID}/action-plan", json={"approved_actions": [ITEM]})
    assert r.status_code == 400 and "consent" in r.json()["detail"].lower()
    assert client.get(f"/api/seller/{SID}/action-plan").json()["items"] == []

    r = client.post(f"/api/seller/{SID}/action-plan", json={"approved_actions": [ITEM], "consent_confirmed": True})
    assert r.status_code == 200
    saved = r.json()["items"][0]
    assert saved["simulated"] is True and saved["status"] == "Draft (simulated)"
    assert len(client.get(f"/api/seller/{SID}/action-plan").json()["items"]) == 1

    client.post("/api/reset", json={"seller_id": SID})
    assert client.get(f"/api/seller/{SID}/action-plan").json()["items"] == []


def test_call_summary_roundtrip(client):
    body = {"summary": "s", "decisions": ["a"], "follow_up": "f"}
    assert client.post(f"/api/seller/{SID}/call-summary", json=body).status_code == 200
    got = client.get(f"/api/seller/{SID}/call-summary").json()
    assert got[0]["follow_up"] == "f"


def test_call_flow_over_http(client):
    s = client.post("/api/call/start", json={}).json()
    sid = s["session_id"]
    assert "prototype" in s["reply"].lower() and "sample seller data" in s["reply"].lower()

    def say(t):
        return client.post(f"/api/call/{sid}/message", json={"text": t}).json()

    r = say("my orders have gone down")
    assert "get_period_comparison" in r["tools_used"] and "identify_sales_drivers" in r["tools_used"]
    assert r["plan"] is None
    r = say("yes in three days")
    r = say("I need to keep my margin, don't reduce the price automatically")
    assert r["stage"] == "consent" and r["plan"] is None and r["proposed"]    # proposed, not saved
    r = say("yes please save it")
    assert r["plan"] and r["plan"]["items"] and r["proposed"] == []
    r = say("no that's all")
    assert r["call_ended"] is True
    summaries = client.get(f"/api/seller/{SID}/call-summary").json()
    assert len(summaries) == 1 and summaries[0]["decisions"]


def test_end_endpoint_and_unknown_session(client):
    sid = client.post("/api/call/start", json={}).json()["session_id"]
    r = client.post(f"/api/call/{sid}/end").json()
    assert r["call_ended"] is True and r["plan"] is None
    assert client.post("/api/call/zzz/message", json={"text": "hi"}).status_code == 404
