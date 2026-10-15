---
# Claims the interview found are believed but not yet checked. The coach adds them; people test and close them.
assumptions:
  - claim: ""
    kind: assumption      # assumption | belief
    status: open          # open | testing | confirmed | rejected
    evidence: ""          # what we have so far
    test: ""              # how to check it, cheaply
    owner: ""
    affects: []           # message, product or customer ids that rest on it
    raised: 2026-01-01
---

## Assumptions

When an assumption is confirmed, move the evidence into the product, customer or message it supports. When it is rejected, fix whatever rested on it.
