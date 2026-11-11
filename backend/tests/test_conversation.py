"""Multi-turn paths through the dialogue controller (no HTTP, no LLM)."""
import json
import pytest
from app import agent, tools, llm

SID = "DEMO-1042"


def new_call():
    s, greeting = agent.start_call(SID)
    return s, greeting


def say(s, text):
    return agent.handle_turn(s, text)


def keys(plan=None):
    return [i.key for i in tools.get_action_plan(SID).items]


def test_greeting_discloses_prototype_once():
    s, g = new_call()
    assert "prototype" in g and "sample seller data" in g and "not a live" in g
    assert g.rstrip().endswith("?")


def test_full_demo_path_to_consented_plan():
    s, _ = new_call()
    r1 = say(s, "My orders have gone down quite a bit. I am not sure what is wrong.")
    assert r1.startswith("I can see that.") and "down 30%" in r1 and "from 500 to 350" in r1
    assert "4%" in r1 and "3.1%" in r1 and "9 days" in r1
    assert r1.rstrip().endswith("?") and "fresh stock" in r1
    assert keys() == []                                    # nothing saved yet

    r2 = say(s, "Yes, I can restock it in three days.")
    assert "lowest price" in r2
    assert s.facts["restock_days"] == 3

    r3 = say(s, "I need to maintain my margin. I can review the price, but do not reduce it automatically.")
    assert "Shall I save" in r3 and "simulated" in r3 and "no automatic change" in r3
    assert s.stage == "consent" and keys() == []           # drafted, still not saved

    r4 = say(s, "Yes, that captures it.")
    assert "not applied to a live Snapdeal account" in r4 and "First checkpoint: restock the organizer in 3 days" in r4
    plan = tools.get_action_plan(SID)
    assert {"restock", "returns_review", "price_review", "dispatch_fix", "traffic_check"} == {i.key for i in plan.items}
    assert all(i.simulated and i.status == "Draft (simulated)" and i.consent == "Approved by seller" for i in plan.items)
    assert plan.items[0].key == "restock" and plan.items[0].timeframe == "Within 3 days"
    # price stays a manual review: no price-change item was created
    assert "price_test" not in keys()

    r5 = say(s, "No, that's all. Thanks.")
    assert s.ended and "recap" in r5.lower()
    assert len(tools.get_call_summaries(SID)) == 1


def test_no_reply_claims_a_live_change():
    s, _ = new_call()
    replies = [say(s, t) for t in ["orders are down", "yes in 3 days", "I can go down to 850 rupees", "yes"]]
    joined = " ".join(replies).lower()
    for bad in ("i've changed", "i have changed", "i've updated your", "i reduced", "price has been"):
        assert bad not in joined


# ----- branches: the seller's answers change the plan -----

def test_restock_branch_none_vs_soon():
    s, _ = new_call()
    say(s, "my sales are down")
    say(s, "I don't have stock, can't restock right now")
    say(s, "I don't know my margin")
    say(s, "yes")
    items = {i.key: i for i in tools.get_action_plan(SID).items}
    assert items["restock"].kind == "investigation" and "Plan around" in items["restock"].title
    assert items["restock"].spoken == "plan around the organizer stockout"

    tools.reset_demo(SID)
    s, _ = new_call()
    say(s, "my sales are down")
    say(s, "yes, in two days")
    say(s, "I don't know")
    say(s, "yes")
    items = {i.key: i for i in tools.get_action_plan(SID).items}
    assert items["restock"].kind == "inventory" and items["restock"].timeframe == "Within 2 days"


def test_price_branches():
    def run(answer):
        tools.reset_demo(SID)
        s, _ = new_call()
        say(s, "orders are down")
        say(s, "yes in 3 days")
        say(s, answer)
        say(s, "yes")
        return {i.key: i for i in tools.get_action_plan(SID).items}

    strict = run("I cannot reduce the price at all")
    assert "price_review" not in strict and "price_test" not in strict and "returns_review" in strict

    manual = run("I can review the price but don't change it automatically")
    assert "price_review" in manual and "price_test" not in manual

    open_ = run("my lowest is 850 rupees, I can go down to that")
    assert "price_test" in open_ and "₹850" in open_["price_test"].title
    assert open_["price_test"].consequential and "Draft" in open_["price_test"].title

    no_room = run("my minimum is 950 rupees")
    assert "price_test" not in no_room and "price_review" in no_room       # floor above current price

    unknown = run("I don't know")
    assert "price_test" not in unknown and "price_review" in unknown


# ----- consent -----

def test_no_consent_means_no_plan():
    s, _ = new_call()
    say(s, "orders are down")
    say(s, "yes 3 days")
    say(s, "I don't know")
    r = say(s, "no")
    assert "nothing is saved" in r and keys() == [] and s.stage == "consent"
    r = say(s, "hmm let me think")
    assert "save" in r.lower() and keys() == []
    say(s, "yes")
    assert keys() != []


def test_create_action_plan_tool_refuses_without_consent():
    s, _ = new_call()
    say(s, "orders are down")
    say(s, "yes 3 days")
    say(s, "I don't know")
    with pytest.raises(tools.ToolError):
        tools.create_action_plan(SID, s.proposed, consent_confirmed=False)
    assert keys() == []


def test_seller_can_drop_an_item_before_saving():
    s, _ = new_call()
    say(s, "orders are down")
    say(s, "yes 3 days")
    say(s, "no price cuts")
    r = say(s, "skip the jar one")
    assert "updated draft" in r and "Shall I save" in r and keys() == []
    say(s, "yes")
    assert "dispatch_fix" not in keys() and "restock" in keys()


# ----- memory / no repeated questions -----

def test_volunteered_answers_are_not_asked_again():
    s, _ = new_call()
    r = say(s, "my orders are down. I can restock the organizer in 3 days and the lowest I can accept on the bedsheet is 850 rupees")
    assert "Shall I save" in r                       # went straight to the plan
    assert "fresh stock" not in r.split("Here's")[-1] and "lowest price" not in r
    assert s.facts["restock_days"] == 3 and s.facts["margin_floor"] == 850


def test_each_question_asked_once():
    s, _ = new_call()
    replies = [say(s, t) for t in ["orders down", "in 3 days", "I can reduce a little, minimum 860"]]
    all_text = " ".join(replies)
    assert all_text.count("fresh stock") == 1 and all_text.count("lowest price") == 1


# ----- awkward input -----

def test_repeat_that():
    s, _ = new_call()
    first = say(s, "orders are down")
    again = say(s, "sorry, can you repeat that?")
    assert again.startswith("Sure.") and first in again


def test_dont_know_and_not_now():
    s, _ = new_call()
    say(s, "orders are down")
    r = say(s, "I don't know")
    assert s.facts["restock_status"] == "unknown" and "restock date" in r

    s2, _ = new_call()
    say(s2, "orders are down")
    r = say(s2, "not now, I'm busy")
    assert s2.ended and "saved no plan" in r


def test_number_is_wrong_is_logged_not_argued():
    s, _ = new_call()
    say(s, "orders are down")
    r = say(s, "that number is wrong")
    assert "can't edit that data" in r and "fresh stock" in r        # still waiting on the same question
    assert s.facts["disputes"]


def test_garbled_answer_reasks_instead_of_guessing():
    s, _ = new_call()
    say(s, "orders are down")
    r = say(s, "the weather is nice")
    assert "didn't quite catch" in r and "fresh stock" in r
    assert "restock_status" not in s.facts


def test_unclear_opening_asks_one_clarifier():
    s, _ = new_call()
    r = say(s, "hello")
    assert "orders, revenue or page visits" in r
    r = say(s, "hello again")
    assert "down" in r or "Visits" in r                     # second time we just proceed


def test_explain_question_answers_then_returns_to_pending():
    s, _ = new_call()
    say(s, "orders are down")
    r = say(s, "why do you think the bedsheet is a problem?")
    assert "not proof" in r and "fresh stock" in r
    assert "restock_status" not in s.facts


def test_ads_and_discount_request_is_handled_carefully():
    s, _ = new_call()
    say(s, "orders are down")
    r = say(s, "should I just run ads?")
    assert "without your approval" in r and "can't promise" in r
    assert keys() == []


def test_concern_changes_the_opening():
    s, _ = new_call()
    r = say(s, "my page visits have fallen")
    assert r.startswith("Yes, page visits are down 10%")
    s2, _ = new_call()
    r = say(s2, "revenue has dropped")
    assert "Revenue is down 30%" in r and "₹3,10,000" in r and "₹2,17,000" in r


def test_product_specific_concern_asks_about_that_product_first():
    s, _ = new_call()
    r = say(s, "my bedsheet sales are down")
    assert "Cotton Bedsheet Set" in r and "lowest price" in r


def test_reads_plan_back_after_saving():
    s, _ = new_call()
    say(s, "orders are down"); say(s, "yes 3 days"); say(s, "no price cuts"); say(s, "yes")
    r = say(s, "can you read the plan back?")
    assert "saved plan" in r.lower() and "simulated" in r.lower()


def test_numbers_come_from_the_data_file(demo_data, tmp_path, monkeypatch):
    demo_data["account"]["previous"] = {"gmv": 248000, "orders": 400, "sessions": 10000}
    demo_data["account"]["current"] = {"gmv": 124000, "orders": 200, "sessions": 9000}
    p = tmp_path / "other.json"
    p.write_text(json.dumps(demo_data))
    monkeypatch.setenv("SELLERPULSE_DATA", str(p))
    s, _ = new_call()
    r = say(s, "orders are down")
    assert "down 50%" in r and "from 400 to 200" in r and "down 10%" in r
    assert "from 500 to 350" not in r


# ----- optional LLM layer cannot change facts -----

def test_llm_rewrite_guard():
    draft = "Orders are down 30%, from 500 to 350. Are you expecting fresh stock of the Bamboo Home Organizer Set this week?"
    assert llm.guard_ok(draft, "Orders are down 30%, 500 to 350 now. Do you expect fresh stock of the Bamboo Home Organizer Set this week?")
    assert not llm.guard_ok(draft, "Orders are down 35%, from 500 to 350. Are you expecting fresh stock of the Bamboo Home Organizer Set this week?")
    assert not llm.guard_ok(draft, "Orders are down 30%, from 500 to 350, and I've changed your price. Fresh stock?")
    assert not llm.guard_ok(draft, "Orders are down 30%, from 500 to 350. Tell me about the Mega Sale Product stock.")
    assert not llm.guard_ok(draft, "Orders are down 30%, from 500 to 350, so restock the Bamboo Home Organizer Set this week.")  # drops the question


def test_llm_used_only_when_guard_passes():
    llm._transport = lambda msgs: "Orders are down 30%, from 500 to 350, which is worrying. Are you expecting fresh stock of the Bamboo Home Organizer Set this week?"
    s, _ = new_call()
    r = say(s, "orders are down")
    assert "worrying" not in r                         # the full reply has other numbers; guard rejected the short rewrite

    seen = []
    def fake(msgs):
        seen.append(msgs)
        draft = msgs[-1]["content"].split("DRAFT:\n")[1]
        return draft.replace("Done.", "All done.")
    llm._transport = fake
    s, _ = new_call()
    for t in ["orders are down", "yes 3 days", "no price cuts"]:
        say(s, t)
    r = say(s, "yes")
    assert r.startswith("All done.") and seen
    assert keys() != []


def test_llm_failure_falls_back_to_rules():
    def boom(msgs):
        raise RuntimeError("quota exceeded")
    llm._transport = boom
    s, _ = new_call()
    r = say(s, "orders are down")
    assert "down 30%" in r


def test_llm_classify_used_only_for_unclear_replies():
    llm._transport = lambda msgs: "dont_know"
    s, _ = new_call()
    say(s, "orders are down")
    say(s, "hmm let me check on that stock thing")       # rules can't read it; LLM label drives it
    assert s.facts["restock_status"] == "unknown"


def test_llm_http_request_shape(monkeypatch):
    """No live provider call here: check we build the request the OpenAI-compatible protocol expects."""
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1/")
    captured = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "  yes  "}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        return FakeResp()

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.enabled() and llm.info()["model"] == "some-model"
    assert llm.classify("sure go ahead") == "yes"
    assert captured["url"] == "https://example.invalid/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert captured["body"]["model"] == "some-model" and captured["timeout"] <= 10
