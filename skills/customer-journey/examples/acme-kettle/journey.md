---
# Fadell's eight stages (Build, Fig 3.1.1). Rename or trim to fit your business.
stages: [awareness, education, acquisition, product, onboarding, usage, support, loyalty]

# Channels are the columns of the activation matrix.
channels: [Website, Product page, Email, App, Packaging, Social]

touchpoints:
  - id: home
    name: Homepage
    stage: awareness
    channel: Website
    workstream: Shopify/Web
    source: {root: site, glob: "index.html"}
  - id: pdp-pour
    name: Acme Pour product page
    stage: education
    channel: Product page
    workstream: Shopify/Web
    source: {root: site, glob: "products/*.html"}
  - id: welcome-email
    name: Welcome email
    stage: onboarding
    channel: Email
    workstream: Email/Klaviyo
    source: {root: email, glob: "*.md"}
  - id: app-setup
    name: App setup strings
    stage: onboarding
    channel: App
    workstream: App
    source: {root: app, glob: "strings.json"}
  - id: box
    name: Retail box
    stage: acquisition
    channel: Packaging
    workstream: Brand
    source: {type: manual}
    notes: Dieline PDF lives with the packaging vendor. Export text to collect it.
  - id: instagram
    name: Instagram
    stage: awareness
    channel: Social
    workstream: Social
    source: {type: manual}
---

## Customer journey

Every stage a customer passes through, and the touchpoints where they meet us.
The front matter is the source of truth; edit it in Obsidian's Properties view or any editor.

Source types:

- `{root: <name>, glob: <pattern>, exclude: <pattern>}` reads files under a root from `journey.config.yaml`
- `{type: url, url: <url or list>}` fetches live pages
- `{type: text, text: <string or list>}` pastes copy inline (good for packaging or ads)
- `{type: manual}` marks a touchpoint the audit cannot see yet; it shows up as a blind spot
