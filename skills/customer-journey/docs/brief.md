## Briefs

A brief is the contract for a page or a marketing asset, written before copy or design starts. It turns the workspace (who we serve, what we say, what we must never say, what the journey needs) into decisions about one page: what it is for, what someone should remember, and how each section earns its place. Copy skills and design tools write from approved briefs; the audit checks the result.

Use it for a website rewrite (one brief per page), a new landing page, or an asset with structure (an email, an ad set, a launch post).

### Inputs

| Source | What the brief takes from it |
|---|---|
| `company.md` | The one metric the page serves, the category word, trademarks and usage rules, role models |
| `customers/` | Who arrives, their pains in their words, objections, triggers |
| `products/` | What is true and provable, what is upcoming and must not be implied |
| `messaging/` | Approved wording, retired wording to avoid, the want / pain / painkiller grid, proof |
| `activation.md` | Which messages this channel must carry |
| `claims.md`, `voice.md` | Guardrails and voice |
| `assumptions.md` | Claims the page would lean on that are not yet tested (flag them) |
| `journey.md` | The page's stage, the touchpoint before and after it |
| `audit/` | Findings on the page being replaced, so the rewrite does not repeat them |

A page that does not exist yet is added to `journey.md` as a touchpoint with `status: planned` (and `replaces:` when it takes over an existing page), so the audit knows to expect it.

### The forcing question

Ask it first, and keep asking it: **what is the one thing someone should remember?**

- For the page: one sentence a visitor could repeat to a friend. If the human gives two, ask which one wins.
- For every section: one takeaway that serves the page's one thing. A section with no takeaway is cut. A section with two is split, or one of them moves elsewhere.
- Every later choice (headline, image, order, CTA) is checked against it.

### Story order

- **Pain before painkiller.** People have stopped noticing the problem (habituation), so the page reminds them of it before offering relief. Fadell calls this the virus of doubt.
- **Rational and emotional reasons**, then **technology simple enough to retell**.
- **Hand-offs.** State what the previous stage promised (an ad, a search result, an email) and keep that promise above the fold. State what the next stage needs (checkout, setup, a help article) and set it up.
- **Emotional arc.** Storyboard the page as scenes, each with a mood and a beat: for example "the 10 pm problem, uneasy", "the shift, calm", "the morning, relieved", "the proof, confident", "the decision, ready". A flat arc is a sign the page is a feature list.
- **Press release test.** If the page's headline and first paragraph were a press release, would it be news? If not, the one thing is not sharp enough yet.

### Safe and risk

Name what the category expects (layouts, claims, imagery, CTAs a visitor will look for) and keep enough of it that the page is easy to use. Then choose **at least two deliberate risks**: places the page departs from the category on purpose so it is remembered. Each risk says what it is, why it serves the one thing, and how you would know it failed.

### Sections

For each section, in order:

- **One thing:** the takeaway
- **Job:** what the section does in the arc (provoke, explain, prove, reassure, ask)
- **Messages:** message ids and their approved wording; no retired wording
- **Proof:** the facts the claims rest on (from `proof` or products); a claim without proof is cut or flagged
- **Claims to avoid:** guardrails that apply here
- **CTA:** names its outcome ("Set your first sunrise", not "Learn more"), or none if the section should not ask
- **Rating:** 0 to 10, and what would make it a 10

Rate after drafting. Resolve gaps with the human one at a time, starting with the lowest score. Do not move on while a section is below 7 without the human agreeing to accept it.

### Verification

Write how the page will be checked at launch:

- Run the audit against staging (a `url` or file source for the planned touchpoint): no high findings, every planned message present, no retired wording.
- A guided review of the staged page with the human (first impression, one thing, hand-offs).
- The assumptions the page relies on, and whether they were confirmed in time.

### Lifecycle

`briefs/<page-id>.md` starts as `status: draft` and becomes `approved` when the human signs off. Changes after approval go in the brief's changelog. When the page ships, the brief stays as the record of intent that future audits and reviews compare against.

### Credits

The forcing question, the safe and risk split, per-section 0 to 10 ratings with "what would make it a 10", and the emotional arc storyboard are adapted from the `design-consultation` and `plan-design-review` skills in [garrytan/gstack](https://github.com/garrytan/gstack) (MIT, Copyright (c) 2026 Garry Tan). Pain before painkiller, the virus of doubt, the press release test and the whole-journey view come from Tony Fadell's *Build*.
