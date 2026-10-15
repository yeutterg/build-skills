## The interview

A deep, multi-session conversation that turns what a company knows (much of it in people's heads) into the workspace: `company.md`, `products/`, `customers/`, `journey.md`, `messaging/`, `activation.md` and `claims.md`. Everything else in the framework stands on it, including any website rewrite.

### Principles

The interviewer is the coach described in `coach.md` (a Fadell-style mentor) unless the workspace turns the persona off. The principles below apply either way.


- **Research before asking.** Never ask what can be read. Crawl the site, read the repos, docs, decks, reviews, app store listings and support macros first. Every question should start from evidence: *"Your site lists five products; three look like accessories. Is Atmos the hero, or Bedtime Bulb?"*
- **Propose, then ask.** Offer a draft answer drawn from the materials and ask the person to confirm, correct or replace it. Editing is faster and surfaces disagreement better than a blank prompt.
- **One topic at a time.** Ask one question, or a tight group of two or three on the same point. Wait for the answer.
- **Dig.** Every important answer gets at least one probe: *why? for example? how do you know? what would change your mind? who disagrees?* Stop probing when the answer is specific enough to write down and check.
- **Customer words over company words.** Capture verbatim phrases from reviews, support mail and sales calls. They become `want` and `pain` lines and `signals`.
- **Surface contradictions.** When what the person says differs from what the materials say, show both and ask which is true. Record the answer and the reason.
- **Separate fact from assumption.** Label each substantive claim `fact`, `anecdote`, `assumption`, `belief` or `goal` (see `coach.md`). Messaging can rest on facts and anecdotes; assumptions go to `assumptions.md` with a cheap test and an owner; goals go to `company.md`.
- **Write as you go.** After each section, update the workspace files and append the session log. An interrupted interview must lose nothing.
- **Respect "skip" and "later".** Record open questions in the session log and come back to them. Some answers need someone else (the person who runs support, the founder, an agency).

### Phase 0: Discover (no questions yet, beyond where to look)

Ask only for: the public website URL, where existing materials live (repos, folders, docs, decks, brand guide, analytics exports), and who else should be consulted. Then, without further questions:

1. `journey.py crawl <ws> --url <site>` for the page inventory and products (`discovery/site.md`, `discovery/products.md`, draft `products/*.md`).
2. Read what exists: brand or style guides, positioning docs, pitch decks, press releases, FAQs, help center, app store listings, marketplace listings, review exports, support macros, email templates.
3. Draft a one-page **What I found** in the session log: products and prices, how the site is organised, the claims and themes the copy leans on, apparent audiences, visible touchpoints by stage, inconsistencies already visible, and the gaps no material answers.

Open the conversation by walking the person through it. It shows the work and resets their expectations of what they need to explain.

### Phase 1: Company and goals → `company.md`

- What does the company do, in one sentence a customer would use? In one sentence an investor would use? Why are they different?
- Why does it exist? What did the founders see that others missed? (Fadell: the *why* before the *what*.)
- **What is the one metric that matters?** The single number that, if it moves, means the company is working right now: revenue, units, active owners, retention, conversion. Everything else should explain or drive it. Ask for the target, a stretch target, the date, today's baseline, and why this metric and not another.
- Break it down together: which drivers multiply into it (traffic x conversion x price, or customers x repeat rate), what each must be, and what each is today. Flag every driver with no baseline as an assumption.
- **Keep it simple.** One number, stated plainly ("$1M of revenue by October"). Do not bolt qualifiers onto it (full price only, happy customers only); if a quality matters, record it as a secondary metric instead. The founder decides how simple; when they say "keep it simple", the coach drops the qualifiers and moves on.
- **Secondary metrics.** Two or three numbers that explain the health behind the one metric without competing with it (for example activation, retention, returns). Record them separately; they are watched, not targeted.
- Pressure-test it: is it the right metric for the stage (a v1 proves demand; a v3 optimizes profit)? What would you refuse to do to hit it (discounts, burning supply, claims you cannot back)? Which constraint binds first: demand, supply, cash, or team?
- What other goals matter for the next 12 months (a launch, a market, a hire), and which one wins when they conflict with the one metric?
- What stage is each product line at: v1 (proving the idea, early adopters), v2 (fixing what's wrong, widening), v3 (optimizing the business)? Fadell's three generations change what marketing must do.
- What constraints shape messaging: regulation, claims you cannot make, certifications, channel agreements, budget, team size?
- What is this work for: a rewrite of the website, a launch, ongoing improvement, fixing a known problem? What does success look like in three months?
- What would you write in the launch press release for the company today? (Draft it together if none exists.)

Done when: the goals have metrics, the stage is named, and the person agrees with a one-sentence description you read back.

**The founder.** What are you great at, and what do you need to get good at for this goal? What makes hard work enjoyable for you? Record it in `founder.md` so the coach can stretch you in the right places.

### Phase 1b: Names, marks and the word you want to own → `company.md` (`category`, `trademarks`)

**The category word.**

- What is one word or phrase you want the company to be known for inventing, or for defining the category of? (The term people will use when they recommend you without naming you.)
- Does that term already exist? If people search for it today, who owns it in their minds: a competitor, academics, nobody? If it does not exist yet, what will it cost to teach it?
- Can you define it in one sentence a customer would repeat? What is in the category and what is not?
- Is there evidence you can be the credible owner: first to market, the best product, the research, the people?
- Where must it appear for you to own it: homepage, product names, press, search, packaging, the help center, how support answers the phone?
- How does it sit with the brand's positioning? (A science-sounding category word can pull against a design-first brand, and the other way round.)

The crawl and audit show how often the term appears today. Record the term, a one-sentence definition, variants to count, and status (`claiming` or `established`). Then add it as a priority-1 message in `messaging/` so the activation matrix plans it everywhere it must appear.

**Trademarks.**

- Which names, marks and logos are registered, which are pending, and which are used without registration? In which countries and classes? Registration numbers?
- Feature and technology names: are they marks you intend to protect, or descriptive names?
- What are the usage rules: ™ or ® on first mention per page, on every mention, never in headlines? Exact capitalization and spacing?
- Are any names at risk (a conflict with another company's mark, like a product name that collides with a well-known brand) or under review?
- Who decides: in-house, a lawyer, nobody yet? (Record "nobody yet" as an open question.)

Record each mark with `status` (`registered`, `pending`, `unregistered`, `unknown`), `symbol`, `usage`, and whether to check capitalization. The audit flags ® on anything not registered (high), missing symbols where the rules require them, and misspelled marks.

A category term is usually generic and cannot be a trademark. Owning a category is about association, not legal protection; trademarks protect the names you put inside it.

### Phase 2: Products → `products/*.md`

Start from the crawl's draft files. For each:

- Confirm or merge. Bundles, preorders, regional variants and old listings are often the same product. Record `aliases` so old handles map to one id.
- What job does it do, for whom? What do people use instead today? What pain makes them switch?
- What is true and provable about it: specs, test results, certifications, lifespan, warranty? (These become `proof`.) Which claims have you been told not to make?
- What generation is it, and what changed from the previous one? Which features are shared across products and which must never be attributed to the wrong one?
- How is it bought: price, channels (own site, marketplaces, retail), bundles, subscriptions, delivery times, return policy?
- How is it set up and used: what's in the box, app or account needed, the first five minutes, the first week, what breaks?

Then **upcoming products**, which the crawl cannot see:

- What is in development, roughly when, at what price, for whom? Which current product does it extend, replace or cannibalize?
- What can be said publicly now, what is embargoed, and what must not be implied yet (for example, "works with" claims before certification)?
- How should today's messaging leave room for it (naming, platform language, roadmap pages)?

Done when: every published product is confirmed, merged or marked discontinued; upcoming products have status `upcoming` with what may be said; every product names its personas.

### Phase 3: Customers → `customers/*.md`

Ask for evidence before opinion: order exports, customer lists, reviews, support history, survey results, analytics audiences. Mine reviews and support mail for verbatim pains and benefits before the conversation.

- **Existing customers.** Who actually buys today? Segment them by what differs in why and how they buy (not demographics alone). Roughly what share of revenue or orders is each? How do you know?
- **Ideal customer (ICP).** Who do you want more of, and why them: margin, retention, word of mouth, strategic fit? How do they differ from today's buyers?
- **Jobs.** Functional, social and emotional jobs each segment hires the product for.
- **Pains.** In their words. Which pain are they aware of, and which have they habituated to (Fadell's virus of doubt)?
- **Triggers.** What happens right before someone starts looking? Where do they look first?
- **Objections.** Why do people hesitate or not buy? Price, trust, compatibility, complexity, aesthetics, doubt about the science?
- **Decision.** Who decides, who influences, who pays? How long from first visit to purchase?
- **After purchase.** What surprises them, good and bad? What do they ask support? What makes them recommend it, or return it?
- **Who it is not for.** Customers you do not want, and wording that attracts them.

Done when: each segment has a share estimate with its source, ranked pains with at least one verbatim quote each, top objections, and the channels where they find you.

### Phase 4: Market and positioning → `company.md` (`alternatives`, `role_models`)

**Competitors and why you're different.**

- Who are your competitors: direct rivals, adjacent products customers compare you with, and the workaround or "do nothing" option? Name them.
- For each: why do people choose them? Where are they genuinely better than you? What is your difference, and would their customers agree it matters?

**Who you look up to.**

- Which companies in adjacent product spaces do you admire, and what exactly would you borrow: the site, the story, the onboarding, the pricing, the community, the way they own a category?
- What would you deliberately *not* copy from them?

Role models shape the rewrite more than competitors do; record them with what to borrow and what to avoid.

- What does a customer use instead: competitors, workarounds, doing nothing? Why do people choose each?
- What is the one thing you do that the alternatives do not? Would customers agree? What proof do you have?
- "Positioning is about what you replace." Which habit or product does yours replace in the customer's life?
- Which brands do your customers also love? What do they borrow from them in taste and expectations?

### Phase 5: Touchpoints and stack → `journey.md`, `journey.config.yaml`

Walk the eight stages with the crawl's site inventory open. For each stage ask what the customer sees, hears and does, then record every touchpoint with an owner and a source.

| Stage | Prompt |
|---|---|
| Awareness | How do people first hear of you: search, social, press, referrals, ads, marketplaces, retail? |
| Education | Where do they learn: site pages, blog, comparison content, email, video, reviews? |
| Acquisition | Where and how do they buy: checkout, marketplaces, retail, B2B; order and shipping emails; delivery? |
| Product | What is the experience of the product itself: design, controls, performance, on-device text? |
| Onboarding | Box, quick-start, account creation, app pairing, welcome emails, setup videos? |
| Usage | App, updates, notifications, changelogs, everyday reliability? |
| Support | Help center, FAQs, contact forms, support replies, warranty, returns, community? |
| Loyalty | Newsletter, reviews and responses, referrals, new products, promotions? |

For each touchpoint: **where does the copy live, and how can the audit read it?** This is where the company's stack goes into the workspace (see `stacks.md`): a CMS repo, a theme, an export, an API, a URL, or pasted text. Anything that cannot be read yet stays `manual` and becomes a blind spot. Ask who owns each touchpoint and record it as `workstream`.

### Phase 6: Messaging → `messaging/`, `activation.md`, `claims.md`

With the evidence from phases 2-4 on the table:

- For each product and top segment, fill Fadell's grid: why I want it, what's my pain (word and sentence), painkiller (sentence and word). Draft from customer quotes, then refine together until the person would put it on the box.
- Rank the pillars. If a customer remembers one thing, which?
- Names, taglines, mission and about text: what is approved, what is retired, what is undecided? Record undecided items as `status: pending` instead of guessing.
- Collect claim guardrails: legal and regulatory limits, words the brand avoids, specs that belong to one product only.
- Plan the activation matrix: which messages each channel must carry. Priority 1 nearly everywhere; depth only where the customer is ready for it.

### Phase 7: Close each session

- Read back the decisions in plain language and confirm them.
- List open questions with an owner.
- Run `validate` and `run`, and show the first or refreshed audit summary.
- Agree the next session's focus.

### Session log

Each session gets `interview/<date>.md`: who took part, phases covered, decisions (with the reason and how they are known), verbatim quotes worth keeping, contradictions found and how they were resolved, and open questions with owners. The log is an input like `reviews/`: written with the person, never regenerated.
