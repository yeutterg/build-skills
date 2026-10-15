## Pricing methods

Short, practical notes on each technique the skill uses. Sources at the end.

### Economic value estimation (EVE)

The value of a product to a customer segment is what the next-best alternative costs them, adjusted for how the product is better or worse.

```
economic value = reference value + positive differentiation − negative differentiation
```

- **Reference value:** the total cost of the alternative the customer would actually choose, not the cheapest thing on the market. Include what they must also buy or do (accessories, setup, subscriptions, time).
- **Positive differentiation:** monetary value (money or time saved, things no longer needed) plus psychological value (design, status, confidence, delight). Psychological value is real but harder to price; estimate it from evidence such as premiums paid for comparable brands.
- **Negative differentiation:** switching cost, learning, risk of an unknown brand, missing features.

Price is then set **below** economic value, leaving the customer a reason to buy. Where it sits between cost and economic value is a strategic choice: lower to win adoption (v1), higher to capture value once it is proven.

Example (fictional): Acme Pour's segment would otherwise buy a 70 variable-temperature kettle. Exact temperature saves ruined tea worth about 40 a year; quiet operation and design are worth perhaps 30 to this design-minded segment; an unknown brand costs about 20 in perceived risk. Economic value ≈ 70 + 40 + 30 − 20 = 120. A price of 99 to 119 leaves the buyer a surplus.

### Value drivers by segment

Segments differ in what they value. For each segment in `customers/`, list:

- **functional** drivers (the job done, time, money, reliability)
- **emotional** drivers (how it feels to own and use)
- **social** drivers (what it says about the buyer)

Then check `messaging/`: every driver used to justify the price should be visible in the story, and every claimed benefit should be one the segment pays for.

### Willingness-to-pay research

**Customer conversations.** Ask about behaviour and context, not hypothetical prices:

- "What were you using before? What did that cost you, all in?"
- "What else did you look at? Why not that?"
- "What almost stopped you from buying?"
- "If this disappeared tomorrow, what would you do?"
- "When you saw the price, what did you compare it with?"

Avoid leading questions ("Isn't 299 a great deal?") and asking people what they would pay in the abstract; stated intent overestimates.

**Van Westendorp price sensitivity meter.** Ask four questions about a clearly described product:

1. At what price would it be so cheap you would doubt its quality? (too cheap)
2. At what price would it be a bargain? (cheap)
3. At what price would it start to feel expensive, though you would still consider it? (expensive)
4. At what price would it be too expensive to consider? (too expensive)

Plot the cumulative curves; the crossings give a range of acceptable prices and a point of marginal cheapness and expensiveness. Needs about 30 or more respondents from the target segment. It gives a range, not a demand curve.

**Gabor-Granger.** Show one price at a time and ask purchase likelihood; move up or down depending on the answer. Gives a rough demand curve near the tested prices, and so the revenue-maximizing point among them. Best for products whose category buyers already understand.

**Conjoint-lite.** Present two or three configurations with prices and ask which they would choose (repeat with variations). Useful for tiers, bundles and feature trade-offs. Full conjoint needs specialist tools and larger samples; the lite version is for direction, not precision.

**Live tests.** Stated preferences are cheap; behaviour is evidence. Options: a staged price change with conversion tracked; landing-page variants that take a deposit or waitlist sign-up; time-boxed offers to segments of an email list. Agree the success metric and rollback threshold before starting.

### Reference prices and anchoring

Buyers judge a price against a reference: the alternative's price, a peer brand's price, the previous price, or the cost per day of use. Choose the reference the page presents deliberately: the alternative's total cost or a premium peer anchors upward; cost per year of use makes a durable product feel cheaper. The reference must be true.

### Introductory and list prices

An introductory price lowers the barrier for early customers while the list price establishes the product's value. Keep it honest: label it as introductory, state or plan when it ends, and make sure the list price is then genuinely charged. A former-price ("was") comparison is lawful only if that price was actually charged in good faith for a reasonable period (FTC, 16 CFR Part 233; the EU Omnibus Directive uses the lowest price in the prior 30 days).

### Price increases

- Tie increases to added value: a v2 feature, new proof, better packaging or service.
- Stage large increases and test each step.
- Grandfather existing customers or open orders where goodwill matters, with a clear end date.
- Tell customers early and plainly what changes and why.

### Discounts and offers

A discount is a cost. Compute it as discount × units taken up, and compare it with the CAC of winning that customer another way. A deliberate loss to migrate loyal customers of a discontinued product to its replacement can be cheap acquisition: they already trust the brand and become reachable owners. Cap and date offers so they do not become the real price.

### Good-better-best and bundles

Tiers work when segments value the product differently: the base tier captures price-sensitive buyers, the top tier captures those who value more. The middle tier is often the target. For a v1 hero product, prefer one price plus at most one bundle (for example with an accessory) until segments are understood.

### Unit economics

Per unit: price − COGS − shipping and fulfilment − payment fees − returns and warranty reserve = contribution. Compare contribution with CAC per channel and compute payback. Fadell's three generations describe the arc: v1 has poor unit economics and high CAC while demand is proven; v2 recoups the investment with a better product and lower costs; v3 optimizes the business for profit. Set expectations for the stage the company is in.

### Sources

- Thomas T. Nagle and Georg Müller, *The Strategy and Tactics of Pricing*, 6th ed. (Routledge, 2017): economic value estimation, value communication, price structure.
- Peter van Westendorp, "NSS Price Sensitivity Meter: A New Approach to Study Consumer Perception of Prices", ESOMAR Congress, 1976.
- André Gabor and Clive Granger, "Price as an Indicator of Quality", *Economica*, 1966.
- US Federal Trade Commission, Guides Against Deceptive Pricing, 16 CFR Part 233.
- Directive (EU) 2019/2161 (Omnibus Directive), Article 6a on price reduction announcements.
- Tony Fadell, *Build* (Harper Business, 2022): v1, v2 and v3 product generations.
