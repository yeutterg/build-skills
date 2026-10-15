## build-skills

Claude Code skills for people who make products, inspired by Tony Fadell's *Build: An Unorthodox Guide to Making Things Worth Making*. Unofficial and not affiliated with the author or publisher.

### Skills

| Skill | What it does |
|---|---|
| [customer-journey](skills/customer-journey/SKILL.md) | A Fadell-style coach interviews you in depth, separating facts from assumptions, about goals, products and customers (after crawling what is already public), keeps your messaging architecture and journey map as markdown, audits every touchpoint against them with automated and guided reviews, writes page and section briefs for a website rewrite, and tracks gaps as GitHub issues |
| [office-hours](skills/office-hours/SKILL.md) | Weekly and ad-hoc founder check-ins: the one metric that matters, last week's assignment, forcing questions on demand and assumptions, and one real-world assignment |
| [design-review](skills/design-review/SKILL.md) | Reviews a page, flow or marketing asset (site, Instagram, ads, email, packaging) for design and message: the one thing to take away, first impression, generic-copy tells, voice and claim checks, graded with a baseline |
| [value-pricing](skills/value-pricing/SKILL.md) | Sets, tests and raises prices with value-based pricing: economic value, willingness to pay, intro vs list price, honest discounts, staged increases |

### How it works

Your company data stays in **your** repo, in a workspace folder of plain markdown. The skills here contain the method and tooling only. Reports are generated as markdown that renders on GitHub and in Obsidian, and are committed so the git history shows the messaging improving over time.

```
your-marketing-repo/            (private)
  journey.config.yaml
  messaging/  journey.md  activation.md  claims.md
  audit/                        generated report
```

See [the framework](skills/customer-journey/docs/framework.md), [the schema](skills/customer-journey/docs/schema.md), and a complete fictional workspace with its generated report in [examples/acme-kettle](skills/customer-journey/examples/acme-kettle/audit/README.md).

### Install

As a Claude Code plugin:

```
/plugin marketplace add yeutterg/build-skills
/plugin install build-skills@build-skills
```

Or copy single skills: `cp -r skills/customer-journey skills/office-hours ~/.claude/skills/` (office-hours, design-review and value-pricing work best alongside a customer-journey workspace).

Then, in your marketing repo: `/customer-journey interview` to build the workspace, `/customer-journey run` to audit, and `/customer-journey review` to review touchpoints together. It works with any stack; see [connecting your stack](skills/customer-journey/docs/stacks.md).

The CLI also runs on its own: `uv run skills/customer-journey/scripts/journey.py run <workspace>`.

### Development

```
python3 -m unittest discover -s skills/customer-journey/tests
```

The example's `audit/` is a golden file; regenerate it with `journey.py run examples/acme-kettle --date 2026-10-15` when output changes on purpose.

### License

[MIT](LICENSE). Some techniques are adapted from [gstack](https://github.com/garrytan/gstack) by Garry Tan (MIT); see [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md).
