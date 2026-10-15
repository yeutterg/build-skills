---
name: value-pricing
description: Set, test and raise prices with value-based pricing, as an interactive session with the founder. Use when the user asks what to charge, wants to set or change a price, plans a price increase, an intro or launch price, a discount or migration offer, good-better-best tiers or bundles, or wants to understand willingness to pay. Works for hardware, consumer products and software. Reads and writes a customer-journey workspace when one exists (company.md, products/, customers/, messaging/, assumptions.md) and records decisions in pricing.md.
argument-hint: "[session | wtp | increase | offer] [workspace path]"
---

# Value Pricing

Price is the most powerful lever a company has and the one founders guess at most. This skill replaces the guess with a method: work out what the product is worth to each customer segment compared with what they would otherwise use, collect evidence of willingness to pay, then set a list price, decide how to launch it, and plan how to raise it.

The method follows value-based pricing as set out in Nagle and Müller, *The Strategy and Tactics of Pricing* (economic value estimation, value communication, price structure), with standard willingness-to-pay research (Van Westendorp 1976; Gabor and Granger 1966). `docs/methods.md` explains each technique; `templates/pricing.md` is the output.

## Workspace

If a customer-journey workspace exists (a folder with `journey.config.yaml`, often `marketing/`), use it. Read before asking anything:

| File | Use |
|---|---|
| `company.md` | `one_metric` (the price must serve it), `stage` (v1, v2, v3), `alternatives` (next-best options and their prices), `role_models` (reference brands and their price points) |
| `products/*.md` | Current `price`, status, generation, `proof` |
| `customers/*.md` | Segments, jobs, pains, objections: the value drivers |
| `messaging/` | The benefits the company already claims; price must match the story |
| `assumptions.md` | Existing pricing assumptions and tests |
| `pricing.md` | Previous pricing decisions, if any |

Write results to `<workspace>/pricing.md` (from `templates/pricing.md`), and add every untested pricing belief to `assumptions.md` with a test and an owner. With no workspace, ask for a folder and create `pricing.md` there.

If the workspace enables the coach (`coach.style: fadell` in `journey.config.yaml`), run the session in that voice (see the customer-journey skill's `docs/coach.md`). Either way: one topic at a time, propose an answer from the evidence, then ask, and label every claim **fact**, **anecdote**, **assumption**, **belief** or **goal**.

## Modes

### session (default): set or review a price

Work through these steps in order. Save to `pricing.md` after each one.

1. **Anchor on the goal.** Read `one_metric`. Translate it into units at candidate prices (for example, a revenue goal of 1,000,000 needs 4,000 units at 250 or 2,857 at 350). Ask which matters more right now: volume (customers, proof of demand, learning) or margin. At v1 the honest answer is usually volume; say so.
2. **Next-best alternative.** For each segment, what would the customer use or buy instead, and what does it cost them in total (price, plus setup, plus the things they must also buy)? This is the reference value. Use `alternatives` and `role_models` as a starting list; ask what is missing.
3. **Differentiation value.** List what makes the product better or worse than that alternative for this segment, and put a money value on each:
   - positive: time saved, money saved, things they no longer need to buy, better outcomes they would pay for, emotional and social value (design, status, peace of mind);
   - negative: what they give up or must learn, risk of a new brand, missing features, setup effort.
   Economic value = reference value + positive differentiation − negative differentiation. Fill the EVE table in `pricing.md`. Mark each number fact or assumption.
4. **Willingness-to-pay evidence.** Show what evidence exists (past prices and conversion, reviews mentioning price, sales conversations, discount take-up). Then propose the cheapest next research step (see `wtp`).
5. **Reference prices and anchoring.** What will the buyer compare the price with on the page and in their head? Which role-model brand sets their expectation? Decide what the page anchors against (the alternative's total cost, the cost per year of use, a premium peer), and never against a price that was not genuinely charged.
6. **Price structure.** One price, or good-better-best tiers, bundles, accessories, subscriptions? Use tiers only when segments value the product differently; a v1 with one hero product usually wants one price and at most one bundle.
7. **Unit economics check.** COGS per unit, shipping and fulfilment, payment fees, returns and warranty reserve, gross margin, customer acquisition cost by channel, and payback. Flag any channel where CAC exceeds gross margin per unit. Fadell's frame: v1 economics are poor and that is acceptable while demand is being proven; v2 should recoup the investment; v3 optimizes for profit. Write which stage the price is set for.
8. **Decide.** Record three numbers: today's price, the target list price, and the floor below which the company will not go. Record why, with labels.

### wtp: plan willingness-to-pay research

Pick the lightest method that answers the question (details in `docs/methods.md`):

- **Customer conversations** with existing buyers and lost prospects: ask about what they compared, what almost stopped them, and what they would do if the product disappeared. Never ask "would you pay X?" cold.
- **Van Westendorp price sensitivity** (four questions: too cheap, a bargain, getting expensive, too expensive) for a range of acceptable prices. Needs 30+ responses from the target segment.
- **Gabor-Granger** (purchase likelihood at a few price points) for a demand curve near the current price.
- **Conjoint-lite** (choose between two or three configurations with prices) when tiers or bundles are in question.
- **Live tests**: price shown to new visitors over a period, landing-page variants with a deposit or waitlist, or a staged increase with conversion tracked. Live behaviour beats stated intent.

Write the plan into `pricing.md` (method, audience, sample size, owner, date) and the assumption it tests into `assumptions.md`.

### increase: plan a price increase

1. Name the trigger: new features or a v2, proven demand (conversion holding), costs, or the end of an introductory price.
2. Choose the path: one step or staged steps, and when. Tie steps to moments that add visible value (a feature release, new proof, better packaging).
3. Decide who keeps the old price (grandfathering existing customers, open orders, waitlist) and for how long.
4. Plan the test: what metric, what threshold rolls the increase back.
5. Write the customer-facing message: what is changing, when, and why, in the brand voice. No pressure tactics that are not true.

### offer: design a discount or special offer

For launch discounts, migration offers (customers of a discontinued product moving to its replacement), referral credits or bundles:

- State the purpose (acquisition, goodwill, learning) and who qualifies.
- Compute the cost: discount × expected take-up, compared with the CAC of acquiring the same customer another way. A loss-making offer can be a sound, deliberate acquisition cost; write it down as one.
- Set an end date and a cap where appropriate, and keep the offer honest (a real deadline, a real list price).
- Record the expected and actual take-up in `pricing.md`.

## Honest pricing

Not legal advice, but non-negotiable in this skill:

- A "was" or strikethrough price must be a price genuinely charged for a reasonable period. In the US the FTC's Guides Against Deceptive Pricing (16 CFR Part 233) cover former-price comparisons; other countries have similar rules (for example the EU's Omnibus Directive requires the lowest price of the prior 30 days).
- An introductory price is fine when it is labelled as introductory and the list price will actually apply afterwards.
- Do not invent scarcity or deadlines. Check claims in pricing copy against the workspace's `claims.md` guardrails.
- When in doubt, recommend the founder checks with counsel before launch.

## Rules

- Every number in `pricing.md` carries a label (fact, anecdote, assumption, belief, goal) and a source.
- Never set a price without writing which stage (v1, v2, v3) it is set for and how it serves the one metric.
- Propose, then ask. The founder decides; record their decision and reason, including when they overrule the analysis.
- Keep `pricing.md` cumulative: dated decision log, never overwrite past decisions.
- Generated markdown stays GitHub and Obsidian compatible: relative links, no wikilinks.
