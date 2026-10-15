---
name: Acme Kettle
url: https://acme-kettle.example
one_liner: A kettle that makes every cup taste the way it should
stage: v1
one_metric:
  metric: Monthly orders of Acme Pour
  target: 1,000 a month
  by: 2027-06
  baseline: 220 a month
  why: Repeat demand from tea drinkers is the thing to prove at v1
  drivers:
    - {driver: Product page sessions, target: "40,000 a month", baseline: "11,000 a month"}
    - {driver: Conversion rate, target: "2.5%", baseline: "2.0%"}
secondary_metrics:
  - {metric: "Returns within 30 days", why: "Early sign the product disappoints", baseline: "4%"}
goals:
  - goal: Prove repeat demand from specialty tea drinkers
    metric: Orders from returning customers
    target: 25% of orders
    by: 2027-06
  - goal: Cut setup support tickets
    metric: Tickets per 100 orders
    target: under 3
    by: 2027-03
category:
  term: precision brewing
  definition: Brewing tea and coffee at the exact temperature each one needs
  variants: [precision-brewing]
  status: claiming
trademarks:
  - mark: Acme Pour
    status: pending
    symbol: "™"
    usage: first-mention
    check_casing: true
    jurisdictions: [US]
    classes: [11]
role_models:
  - name: Fellow
    space: Coffee gear
    borrow: Product pages that teach brewing, not just sell hardware
    avoid: Accessory sprawl
alternatives:
  - name: Stovetop kettle and thermometer
    why: Cheap and familiar
    our_edge: Holds the temperature without watching it
  - name: Variable-temperature kettles from big brands
    why: Available everywhere
    our_edge: Exact to the degree and quiet
constraints:
  - No health claims about water or tea
voice_guide: ""
---

## Why we exist

Good tea and coffee are ruined by water that is too hot. People who care know it, and still guess.
