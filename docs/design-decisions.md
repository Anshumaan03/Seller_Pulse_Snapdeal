# Design decisions

## What I built and why

> **Edit this section after you have read the code.** It is written as a starting draft in first person. Keep what you can explain in your own words, change what does not match your thinking, and delete anything you would not be comfortable defending in the discussion.

The brief was clear about what it did not want: another FAQ bot. So I started from what a Key Account Manager actually does on a call: look at the account before dialling, work out the biggest problem, ask only what they need to know, and leave with an agreed next step.

SellerPulse is that, in a small form. The seller speaks; the agent compares the last 30 days with the 30 before; it breaks the drop into fewer visits and lower conversion; it looks at each product for stockouts, price gaps, returns and fulfilment misses; and it ends with a draft plan the seller has to approve out loud before anything is saved.

I kept two rules from the start. First, every number the agent says comes from a tested Python function, not from a model. Second, nothing consequential happens without a yes, and nothing is ever described as a live change because there is no live system here.

I chose a deliberately small build so that I could get the whole loop (voice in, diagnosis, questions, consent, saved plan) working end to end and explain every part of it, instead of building something wider that I could not demo reliably.

## The business problem

A seller whose sales have dropped usually does not know which of several things is responsible: fewer visits, lower conversion, a stockout, a price gap, returns, slow dispatch. A support FAQ answers "how do I change my price". A KAM is supposed to say "your top product has been out of stock for nine days; can you restock this week?" and then follow it through. That second thing is what this prototype tries to show.

## Why voice-first

Many sellers run small businesses from a phone and are not going to read a dashboard. A call is how a human KAM would reach them, and a conversation lets the agent ask a follow-up the moment an answer matters ("when can you restock?"). The screen is there to support the call: it shows the numbers and the plan, but the conversation is the product.

I used the browser's speech recognition and synthesis because it needs no paid key and runs anywhere Chrome does. The trade-off is that it is turn-based, so there are pauses and no automatic interruption.

## Why diagnosis is deterministic

If a language model did the arithmetic or chose which numbers to quote, it could sound confident and be wrong. A seller deciding whether to restock or change a price on that basis would be harmed by it. So the maths (percentage change, AOV, conversion, SKU gaps, driver ranking) lives in ordinary functions with unit tests. The agent speaks what the functions return. An optional LLM can reword a reply, but a guard throws the rewrite away if any number or name changes.

The diagnosis also separates three things on purpose: *observed* (from the data), *hypothesis* (worded as a lead, never as a cause), and *to verify* (a question or missing data). The price gap, for example, is called "a lead worth testing, not proof of the cause", and returns are not blamed on the listing until the return reason is known.

## Why recommendations need consent

Price, stock and promotion changes have real cost to a seller's margin. The agent reads the draft aloud, asks "Shall I save this plan?", and only a yes saves it. The tool itself refuses to save without a consent flag, so a bug in the conversation cannot skip it. Even then, the saved items are marked "Draft (simulated)". In the prototype the agent never changes anything.

## How actions are ranked

Each action gets a transparent score: impact x3 + urgency x2 + confidence x2 - effort, using High/Medium/Low. Impact comes from the share of the order drop sitting on that product or metric. Confidence is deliberately low for price and fulfilment because the dataset cannot prove cause. No revenue uplift is estimated anywhere, because the data does not support a number.

## What I deliberately did not build

- Real Snapdeal data, APIs, or any action on a live account. Everything is mock.
- A streaming speech-to-speech model. It would feel more natural, but needs a paid key and more time to make reliable.
- Hindi speech output and full Hindi understanding.
- Multiple sellers, authentication, or a deployed public URL.
- Ads or discount recommendations. The data has no ad history, and the brief's own rule is to fix fulfilment before generating more demand.
- Charts. A fake chart with no analytical value would add nothing to a voice call.
- A vector database, LangGraph or other orchestration frameworks. A small state machine is enough and easier to explain.

## Trade-offs worth knowing

- Rule-based understanding is predictable and testable but narrower than an LLM. The optional LLM classifier is a safety net for unclear answers, not the main path.
- The frontend is plain JavaScript rather than React/Vite. Fewer moving parts for the demo; a framework would pay off if the UI grew.
- Data is one fixed pair of 30-day windows. The tools reject other windows instead of guessing.
