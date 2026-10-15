## The framework

`customer-journey` turns three ideas from Tony Fadell's *Build: An Unorthodox Guide to Making Things Worth Making* (2022) into data a tool can check. The book's figures are not reproduced here; buy the book, it's worth it.

### 1. The customer journey is the product

Makers focus on the device and forget the rest of the path. Customers walk all of it, and a missing or misaligned step is where they stumble. Fadell's journey has eight stages, with the product in the middle:

| Stage | Typical touchpoints |
|---|---|
| Awareness | PR, search, social, paid ads |
| Education | Website, email, blog, trial or demo |
| Acquisition | Partners and retailers, payment model, up-sell and cross-sell, delivery |
| Product | Industrial design, UX, performance |
| Onboarding | Quick-start guide, account creation, how-to videos, tips |
| Usage | Reliability, usability, updates, lifespan |
| Support | Troubleshooting, knowledge base, call centre, community |
| Loyalty | New products, newsletter, promotions, ratings and reviews |

In a workspace this is `journey.md`: every touchpoint gets a stage, a channel, an owner, and a **source** the audit can read. Touchpoints it cannot read yet still count; they are listed as blind spots.

### 2. Messaging architecture: why I want it, why I need it

For each reason someone buys, write down:

- **Why I want it**: the desire, in the customer's voice
- **What's my pain**: one word and one sentence. Habituation hides pain, so marketing has to remind people of it before offering the cure
- **Painkiller**: one sentence and one word describing how the product removes the pain

Fadell used this template at Nest and has since passed it on to many startups. Here each row is one file in `messaging/`, with extra fields that make it checkable: the **approved** wording, regex **signals** that the message is present in other words, **retired** wording that must disappear, and **proof** (the numbers the claim rests on).

Product names, taglines, the mission and the about text are messages too. Renames are the most common source of stale copy.

### 3. Messaging activation matrix

Not every message belongs everywhere. The headline benefit goes on the website, packaging, ads and social; technology detail lives on the website and in sales material. The matrix keeps you from overwhelming or under-educating a customer at any one touchpoint. In a workspace it is the table in `activation.md`: messages as rows, channels as columns.

### What the audit adds

The book's matrix is a plan. The audit fills a second, **observed** matrix from what the touchpoints actually say and reports the difference:

| Check | Source | Finds |
|---|---|---|
| `retired` | scan | Old names, taglines and phrasing still live |
| `claim` | scan | Guardrail violations (medical claims, superlatives, legal) |
| `missing` | scan | A message planned for a channel that no collected touchpoint carries |
| `trademark` | scan | ® on unregistered marks, missing ™/® where the rules require it, misspelled marks |
| `contradiction`, `stage-fit`, `pain-first`, `promise-break`, `paraphrase`, `voice` | judgment pass | What only a reader can see |
| `review` | guided human + AI session | Whether the touchpoint works for the customer at this stage, decided together |
| `walk` | persona walkthrough | Friction in the live journey |

Automated checks and guided reviews complement each other: the scan is exhaustive and cheap, so it runs every time; a review is slow and judgment-heavy, so it is scheduled (every touchpoint on a cadence, plus anything about to launch) and its decisions are recorded as notes in `reviews/`.

Findings are grouped into GitHub issues that open, update, reopen and close themselves as runs change. The report is plain markdown committed to the repo, so its git history is a record of the messaging getting better.

### Related ideas worth borrowing

- **Write the press release first** (Fadell, and Amazon's Working Backwards). Use it as the north star for the architecture.
- **Virus of doubt**: make customers feel a pain they had stopped noticing. `pain-first` checks this.
- **v1, v2, v3**: early adopters need the disruption story; later customers need reassurance and proof. Revisit the activation matrix with each generation.
