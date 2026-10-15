## Design review checklists

Reference for `SKILL.md`. Use what fits the asset; a social post does not need a navigation check, and a checkout does not need a thumb stop. Each finding gets a severity: `high` (wrong, risky, blocks the one thing or the task), `medium` (weakens it), `low` (polish).

### Rules by surface job

**Persuade** (landing and product pages, ads, posts, campaign emails)

- The first screen reads as one composition, not a dashboard of equal boxes.
- Brand, then headline, then supporting line, then action, in that order of prominence.
- Hero budget: brand, one headline, one supporting sentence, one call to action group, one image.
- One job per section: one purpose, one headline, one short supporting sentence.
- Readable by headlines alone.
- Show the product, not a stock photo or a placeholder.
- Cards only when the card is the interaction.
- If cutting 30% of the words improves it, keep cutting.

**Operate** (checkout, account, settings, app screens)

- Calm hierarchy, few colors, strong type; the brand lives in the details.
- Utility language: where you are, what is happening, what to do next.
- Every choice is a mindless click: obvious what happens.
- Specific button labels ("Place order", not "Continue").
- Errors say what happened and how to fix it.

**Read** (help articles, blog posts, guides)

- One reading column, about 65 to 75 characters per line.
- Headings sit closer to what follows than what precedes.
- Wayfinding: where am I, what is next, how do I search.
- No hero theater on an index of articles.

**Experience** (galleries, lookbooks, showcases)

- The work fills the first screen; the interface gets out of the way.
- Never crop the work to fit a template.

Mixed pages: classify each section, not the page.

### Instant-fail patterns

Flag as `high` if any apply:

1. A generic grid of feature cards as the first impression
2. A beautiful image with a weak or invisible brand
3. A strong headline with no clear action
4. Busy imagery behind text
5. Several sections repeating the same mood statement
6. A carousel with no narrative purpose
7. Fake proof: invented testimonials, unverifiable numbers, made-up press logos

### Generic and AI-pattern tells

The test: would a respected studio ship this?

- Generic hero copy: "Welcome to...", "Unlock the power of...", "Your all-in-one solution for..."
- "Get started" and "Learn more" as the only calls to action
- Three big numbers with tiny labels under the hero ("10k+ users", "99.9%")
- A testimonial row with avatars, five stars and quotes nobody said
- The symmetrical three-column feature grid: icon in a colored circle, bold title, two lines, three times
- Identical cards for content of unequal weight
- A stock-photo hero, or a gray placeholder where the product should be
- The template hero: headline left, screenshot right, two buttons
- Decorative blobs, floating circles, wavy dividers filling an empty section
- Emoji as design elements in headings or as bullets
- Everything centered; the same large radius on every element
- Purple or blue-to-purple gradients as the default palette; gradient buttons as the main action
- A cookie-cutter rhythm: hero, three features, testimonials, pricing, call to action, every section the same height
- Frosted-glass panels everywhere
- Only the happy path designed: no empty, loading or error states

### Copy

- Happy talk: welcome paragraphs, self-praise, "we are passionate about". Report its share of visible words.
- Instructions longer than one sentence.
- Vague benefit words with no specifics ("better", "smarter", "revolutionary").
- Pain before painkiller on Persuade surfaces.
- Active voice; specific nouns; the customer's words over the company's.
- No lorem ipsum or placeholder text.
- Workspace checks when present: approved wording used, retired wording absent, claim guardrails clean, voice and terminology rules followed, trademark symbols per the rules.

### Visual and accessibility

- One clear focal point per view; the squint test still shows the hierarchy.
- At most three typefaces; body text at least 16 px on the web; captions at least 12 px.
- Contrast: body text at least 4.5:1, large text and interface parts at least 3:1.
- Nothing communicated by color alone.
- Consistent spacing scale; related things closer than unrelated ones.
- Touch targets at least 44 px; clickable things look clickable without hover.
- No horizontal scroll on mobile; the mobile layout makes design sense, not just stacked columns.
- Motion has a purpose, respects reduced-motion settings, and never hides content behind timing.
- Pages load fast enough that the first screen appears without visible shifts.

### Pages and flows

- **Trunk test**: site, page name, major sections, options here, where you are, search.
- **Page area test**: every area nameable in two seconds.
- **Goodwill meter** (start at 70): drains for hidden price, shipping or contact (minus 15), interstitials and forced pop-ups (minus 15), punishing input or asking for unneeded information (minus 10), sloppy appearance (minus 10), a choice that needs thought (minus 5 each), a broken promise from the previous step (minus 10). Fills for an obvious top task (plus 10), costs and limits upfront (plus 5), saved steps (plus 5 each), graceful recovery (plus 10), an apology when something fails (plus 5).

### Social, ads and email

Platform specs change; confirm current values before a launch. Typical values:

| Format | Shape | Watch for |
|---|---|---|
| Feed post or carousel | 4:5 portrait (1080 x 1350) or 1:1 | First slide must work alone; one story across slides |
| Story or reel | 9:16 (1080 x 1920) | Keep text and logos out of roughly the top and bottom 14% (interface chrome) and the right edge (buttons) |
| Feed ad | 4:5 or 1:1 | Primary text truncates around 125 characters; headline short |
| Email | about 600 px wide | Subject plus preview text do the work of a hook; images off by default in some clients |

- **Thumb stop**: the first frame or first line is enough to stop a scroll on its own.
- **Hook within 125 characters**: what shows before "more" carries the one thing.
- **One message per asset.**
- **Call to action** that fits the platform and names its outcome.
- **Legible at phone size**, at arm's length, in sunlight.
- **Captions on video** (most social video plays muted); **alt text** on images; contrast on text over images.
- **Brand visible** without a logo watermark shouting.
- Hashtags and links: few, relevant, after the message.

### Packaging and print

- The one thing readable from shelf distance.
- What is in the box, what you need, and the first step are obvious.
- Legal and regulatory text present but designed, not dumped.
- Trademark symbols and claims follow the workspace rules.
