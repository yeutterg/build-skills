---
rules:
  - id: health-claim
    pattern: '\b(cures?|detox\w*|boosts? (your )?metabolism)\b'
    severity: high
    reason: Health claims need substantiation we do not have.
    suggest: Describe the experience (taste, temperature), not a health outcome.
  - id: superlative
    pattern: '\b(best|world''s first|revolutionary)\b'
    severity: low
    reason: Superlatives read as hype and invite challenge.
---

## Claim guardrails

Patterns that must not appear in customer-facing copy. Each rule is a case-insensitive regex.
Use `except_touchpoints: [id]` when a rule legitimately does not apply somewhere.
