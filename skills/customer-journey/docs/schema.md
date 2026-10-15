## Workspace schema

All inputs are markdown with YAML front matter (edit them in any editor, or Obsidian's Properties view) except `journey.config.yaml`.

### journey.config.yaml

| Key | Meaning |
|---|---|
| `brand` | Name used in report titles |
| `output` | Output folder, default `audit` |
| `roots` | Named source roots for file touchpoints. Relative to the workspace; `~` and `$VARS` expand |
| `github.repo` | `owner/name` where issues are opened |
| `github.label` | Issue label, default `customer-journey` |
| `github.project` | `{owner, number, status}`: adds issues to a Projects (v2) board and sets `Status` (default `Inbox`), `Workstream` and `Priority` (P1-P3) when those single-select fields and options exist |
| `ignore` | List of `{fp, reason}`. `fp` is a finding fingerprint or issue group key from `audit/data/scan.json` |

### messaging/**/*.md

| Field | Meaning |
|---|---|
| `id` | Unique, stable id |
| `kind` | `mission`, `vision`, `about`, `name`, `tagline`, `pillar`, `feature`, `spec`, or your own |
| `title` | Display name |
| `products` | Products it belongs to; empty means company-level |
| `priority` | 1 (everywhere) to 3+ (deep pages). Sets the severity of `missing` findings |
| `status` | `approved`, `pending` or `draft`. Only approved messages raise `missing` findings |
| `want`, `pain`, `pain_word`, `painkiller`, `painkiller_word` | The why-I-want-it / why-I-need-it grid |
| `grid_status` | `approved` (default) or `draft`; drafts are badged in the report |
| `approved` | Canonical wording. A case-insensitive phrase match means the message is present |
| `signals` | Regexes that also count as present (paraphrase, key numbers) |
| `retired` | Wording that must go. Matches become `retired` findings unless nested inside approved wording |
| `retired_severity` | Default `medium`; use `high` for renames |
| `retired_except_touchpoints` | Touchpoint ids where retired wording is legitimate (e.g. a legal entity name on the regulatory page) |
| `proof` | Facts the message rests on; the judgment pass checks touchpoints against them |

The body is free-form notes and rationale.

### journey.md

Front matter keys: `stages` (ordered list, default Fadell's eight), `channels` (activation matrix columns), `touchpoints`.

| Touchpoint field | Meaning |
|---|---|
| `id`, `name` | Stable id and display name |
| `stage`, `channel` | Must match `stages` / `channels` |
| `products` | Products the touchpoint covers; scopes product-specific claim rules |
| `workstream` | Free text; mapped onto the GitHub project's Workstream field |
| `source` | One source or a list of them: `{root, glob, exclude}` files, `{type: url, url}`, `{type: text, text}`, or `{type: manual}` |
| `notes` | Shown on the touchpoint page |

Files are read by type: `.html`/`.liquid` with tags stripped, `.json` as every string value (location `file#key.path`), anything else line by line.

### activation.md

The first markdown table in the body. First column: a message link (`[Title](messaging/x.md)`), id or title. Other columns: channel names. Any of `✓ ✔ ✅ x yes ●` marks a planned cell.

### claims.md

Front matter `rules`: `{id, pattern, severity, reason, suggest, except_touchpoints, products}`. With `products`, the rule only applies to touchpoints tagged with one of them (e.g. a spec that is true for one product and must never appear on another's pages). `pattern` is a case-insensitive Python regex.

### reviews/*.md

One note per guided review session (see `templates/review.md`).

| Field | Meaning |
|---|---|
| `touchpoint` | Touchpoint id, or a list for a hand-off review |
| `date` | ISO date of the session |
| `reviewers` | Who took part |
| `status` | `draft` while in progress, `done` when finished; only `done` reviews count |
| `verdict` | `on-message`, `needs-work` or `off-message` |
| `persona` | Who the reviewers role-played |
| `findings` | Agreed gaps: `{severity, title, location, excerpt, detail, message?}`. Only the latest review of a touchpoint contributes findings |

`journey.config.yaml` `review_every_days` (default 90) sets when a touchpoint is due for another review.

### audit/data/semantic.json

Written by the skill's judgment pass. Array of `{check, severity, title, touchpoint, location, excerpt, detail, message?}`.

### audit/data/pages.json and summaries.json

`render` writes `pages.json`: one entry per page with an executive summary (`README`, `matrix`, `stage:<id>`, `touchpoint:<id>`), giving its file and a `basis` hash of the findings on that page. The judgment pass may write `summaries.json` with `{key: {basis, key_findings, recommendations}}`; a page uses it only while its basis matches, otherwise it falls back to the summary computed from the data.
