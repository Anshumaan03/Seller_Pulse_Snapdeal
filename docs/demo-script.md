# Demo script (about 100 seconds)

You really speak into the microphone and the agent really answers out loud. The agent lines below are what the current build says on this path; yours may differ a little if you improvise, which is fine.

**Before you press record:** headphones in, Chrome open at `http://localhost:8000`, **Reset demo** clicked, system volume up, notifications off. Do one throwaway run first so the mic permission is already granted.

| Time | You do / say | Agent says (approx.) | On screen |
|---|---|---|---|
| 0:00 | Click **Start call**. | "Hi, this is SellerPulse, your virtual account manager. This is a prototype running on sample seller data, not a live Snapdeal account. I've compared your last 30 days with the 30 before. What change have you noticed most?" | State goes Connecting, Speaking, Listening. "Synthetic demo data" badge visible. Snapshot shows GMV, orders, sessions down. |
| 0:22 | **Say:** "My orders have gone down quite a bit. I'm not sure what's wrong." | "I can see that. Orders are down 30%, from 500 to 350. Visits are down 10%, but conversion also slipped from 4% to about 3.1%, so traffic alone doesn't explain it. The Bamboo Home Organizer Set was out of stock for 9 days. Are you expecting fresh stock of the organizer this week?" | Spoken caption under the state. Right panel shows the Observed / Hypothesis split. Optional: flick to **Under the hood** to show the tools called. |
| 0:48 | **Say:** "Yes, I can restock it in three days." | "Good, about 3 days is workable... Two other signals: the bedsheet is priced above the demo benchmark and showing a higher return rate, and the jar has more late dispatches and cancellations than the mock targets. Before we touch pricing, what's the lowest price you could accept on the bedsheet?" | Facts remembered (restock 3 days) appear in Under the hood. |
| 1:12 | **Say:** "I need to maintain my margin. I can review the price, but don't reduce it automatically." | "Understood, I won't change any price. I'll only draft a review for you to decide. Here's the draft plan. Restock the organizer in 3 days, check why visits dipped, review bedsheet return reasons, review bedsheet price against your margin with no automatic change, and look into jar dispatch delays and cancellations. It's a simulated draft... Shall I save this plan?" | **Action plan** tab shows **Proposed plan (waiting for the seller's yes, nothing saved)**. |
| 1:40 | **Say:** "Yes, that captures it." | "Done. The plan is saved in this demo, not applied to a live Snapdeal account. First checkpoint: restock the organizer in 3 days. Anything else before we end?" | Table switches to **Saved plan**: priority, owner, due date, status "Draft (simulated)", consent "Approved by seller". **Stop recording here**, or say "No, that's all, thanks" to hear the short recap and end the call. |

If you want the ending recap on tape, say "No, that's all, thanks" and it will go over the 2-minute mark by 10-15 seconds. Trim it in editing, or stop at the saved plan.

## Say it in your own words

The path above is a test route, not a recording to replay. Change the wording: say "my sales dropped", "haan, teen din mein ho jayega", "I can't go below 880 rupees". The agent takes whatever it understands and asks again for what it did not catch.

## Other branches to know (in case Sourav asks "what if...")

| You say | What changes |
|---|---|
| "I don't have stock right now" | The first action becomes "plan around the organizer stockout" with a restock-date target, not a restock date. |
| "My lowest is 880 rupees, you can test down to that" | Draft includes "draft a bedsheet price test at ₹880, only with your approval" (still not applied). |
| "I can't reduce the price at all" | No price item at all; returns and listing review only. |
| "My minimum is 950" | Above the current price, so no room to cut; price is a review only. |
| "I don't know" (either question) | Plan asks the seller to confirm that detail first; no price change is drafted. |
| "Skip the jar one" at the confirmation | Item removed, draft re-read, nothing saved until yes. |
| "Should I run ads?" | Agent advises holding off until dispatch is fixed and says it will not create promotions without approval. |
| "Repeat that" / "that number is wrong" / "not now" | Repeats; notes the dispute honestly; ends politely with no plan saved. |
