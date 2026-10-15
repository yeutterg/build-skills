---
touchpoint: home            # one id, or a list for a review that spans a hand-off
date: 2026-01-01
reviewers: [Your Name, Claude]
status: done                # draft while the session is in progress
verdict: needs-work         # on-message | needs-work | off-message
persona: ""                 # who we pretended to be
findings:                   # agreed gaps; these become issues like any other finding
  - severity: medium
    title: Short description of the gap
    location: path/or/url
    excerpt: "verbatim copy"
    detail: What we decided to change and why
    message: ""             # optional message id it relates to
---

## Context

Who arrives here, from where, and what they need before the next stage.

## Walkthrough

### 1. First impression (5 seconds)
### 2. Pain first
### 3. Messages that land, and messages that are missing
### 4. Depth for the stage
### 5. Proof
### 6. Voice
### 7. Hand-off to the next stage

## Decisions

- Agreed changes (also listed as findings above)
- Messaging changes to make in `messaging/`
- Accepted as-is, and why
