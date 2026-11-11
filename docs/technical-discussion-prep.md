# Technical discussion prep

Short, honest answers you can say in your own words. If you cannot explain a line here, open the file named next to it and read it first.

## Why SellerPulse and not a normal chatbot?
A chatbot waits for questions. A KAM looks at the account first and takes ownership of the problem. SellerPulse opens already knowing orders are down 30%, works out the biggest contributors, asks only what would change the advice, and ends with an approved plan. *(agent.py: `_opening_findings`, `_advance`)*

## How does the agent know why sales dropped?
It does not claim to know the cause. It computes what changed: orders, GMV, sessions, conversion, then splits the order drop arithmetically into "fewer visits" (about 50 orders) and "lower conversion" (about 100). It then checks each product for stockout, price vs a supplied benchmark, return rate, dispatch and cancellations. Each finding is labelled observed, hypothesis, or to verify. *(analytics.py: `period_comparison`, `identify_drivers`)*

## Which decisions are the LLM's and which are deterministic?
In the default run there is no LLM. The controller decides what to say and ask; the tools produce every number. If an LLM is configured it can only (1) reword a reply and (2) label an unclear answer. It cannot call tools, create plans or change numbers. *(llm.py, `guard_ok`)*

## How do you stop it hallucinating metrics?
Numbers come from tool outputs, never from model text. The reword guard rejects any rewrite whose set of numbers differs from the draft, or that adds a new product-like name, drops the question, or claims a change was made. Tests cover each case. *(test_conversation.py: `test_llm_rewrite_guard`)*

## How would this work with real Snapdeal data and APIs?
Replace `load_data()` and the tool bodies with calls to seller-account APIs (orders, sessions, inventory, returns, fulfilment). The tool signatures and the dialogue controller stay the same. For actions, `create_action_plan` would create tasks or approval requests inside a system I have no access to, which is exactly why it is simulated here. I do not know what APIs exist internally, so I would start by asking what data is available and how fresh it is.

## What if the data is incomplete or stale?
Missing fields stay `None` and are never invented: a SKU with no price has no price gap, and each driver lists its `missing_data`. The tools reject time windows they do not hold. Staleness is not handled in the prototype; with real data I would put a "data as of" timestamp in every tool result and have the agent say so when it is old.

## Why is voice a better fit? Latency and interruption trade-offs?
Small sellers are more likely to take a call than open a dashboard, and a conversation lets the agent ask the follow-up while the answer matters. Trade-offs here: browser speech is turn-based. Recognition ends after a pause, then a server call, then speech, so there is a noticeable gap. Interruption is manual (button or Space) because with open speakers the mic hears the agent. A realtime speech-to-speech API would give lower latency and natural barge-in; I did not use one because it needs a paid key and I could not test it here.

## How do you decide which recommendation comes first?
Score = impact x3 + urgency x2 + confidence x2 - effort, each High/Medium/Low (3/2/1). Impact is the share of the order drop sitting on that product or metric. The organizer ranks first because it is a large share, the stockout is ongoing, and the data is direct. Price and fulfilment rank lower because the link to the order drop cannot be proven from this data. The weights are my judgment, not tuned; with real data I would calibrate them against outcomes. *(analytics.py: `driver_score`; tools.py: `estimate_action_priority`)*

## How do you protect a seller from a harmful price or discount change?
Four layers. The agent asks for the margin floor before drafting a price item. A price item stays a "review" unless the seller gave a floor and allowed a test. Nothing is saved without a spoken yes. And `create_action_plan` raises without a consent flag, so a conversation bug cannot skip it. In a real system I would add a minimum-price guard in the API itself and a revert path.

## How would you measure whether Virtual KAM helps?
Prototype metrics I can measure now: time to diagnosis, how often a call reaches a consented plan, and how often the seller has to repeat themselves. Real-world metrics would need a pilot: action acceptance rate, action completion rate, stockout duration, late-dispatch rate, conversion recovery versus a comparison group, seller retention/engagement and seller satisfaction. I have measured none of the real-world ones; I should not claim any impact.

## What would you build next with another week?
1. A realtime voice layer (streaming speech-to-speech) with real barge-in and Hindi/Hinglish.
2. A proper LLM tool-calling loop on top of the same tools, with the consent guard kept in the tool.
3. A follow-up: after the plan is saved, check back at the due date and report what changed.
4. An evaluation set of simulated sellers (different problems) to measure diagnosis quality.

## Other questions to expect

**Why a state machine and not LangGraph?** Five stages and one consent gate do not need a framework; I can explain every transition.

**Why is conversion decline not its own action?** Conversion is an outcome. The causes are the product-level signals (stockout, price, returns, fulfilment). The traffic action is "investigate" because the data cannot say why visits fell.

**Is "traffic explains 50 orders" a cause?** No. It is an arithmetic split of the order change into a traffic part and a conversion part. The UI says so.

**What did you test?** 56 automated tests (maths, endpoints, conversation branches, consent, LLM guard), a headless-Chrome check of the page with fake audio, and a clean-start run. What I had not tested when this was built: a real microphone, real speakers, and a live LLM key. Say so if asked.

**What is real and what is mocked?** Real: the voice interaction in the browser, the calculations, the dialogue logic, the SQLite storage. Mocked: all seller data, the benchmark and targets, and every action (simulated drafts).

**Did you use AI tools to build this?** The brief allows it. Say which ones you used and what you decided yourself (the scenario logic, the consent rule, the deterministic-maths rule, what to leave out).
