## build-skills

Claude Code skills for people who make products, inspired by Tony Fadell's *Build: An Unorthodox Guide to Making Things Worth Making*. Unofficial and not affiliated with the author or publisher.

### Skills

| Skill | What it does |
|---|---|
| [customer-journey](skills/customer-journey/SKILL.md) | Interviews you in depth about goals, products and customers (after crawling what is already public), keeps your messaging architecture and journey map as markdown, audits every touchpoint against them with automated and guided reviews, and tracks gaps as GitHub issues |

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

Or copy a single skill: `cp -r skills/customer-journey ~/.claude/skills/`.

Then, in your marketing repo: `/customer-journey interview` to build the workspace, `/customer-journey run` to audit, and `/customer-journey review` to review touchpoints together. It works with any stack; see [connecting your stack](skills/customer-journey/docs/stacks.md).

The CLI also runs on its own: `uv run skills/customer-journey/scripts/journey.py run <workspace>`.

### Development

```
python3 -m unittest discover -s skills/customer-journey/tests
```

The example's `audit/` is a golden file; regenerate it with `journey.py run examples/acme-kettle --date 2026-10-15` when output changes on purpose.

### License

[MIT](LICENSE)
