# Multichannel campaign workspace

MENAXVI can create a deterministic, reviewable campaign package in `pt-PT` or
`en-US`. The current channel set is:

- Meta Ads;
- Google Search Ads;
- email;
- organic social.

Choose at least two channels. The package includes positioning, transparent
budget allocation, channel-specific drafts, measurement guidance, launch
checks, assumptions, a claim ledger, a quality review, and one human approval
gate.

## Required business context

The dashboard requires company, audience, offer, objective, geography, brand
direction, channels, locale, total budget, currency, duration, claims,
supporting evidence, constraints, and approval owner.

Claims and evidence must be separated:

```text
Claim: Every quote is reviewed against the customer's stated service needs.
Evidence: The company reviews service needs before confirming a quote.
```

## What MENAXVI does not do

The generator is deterministic and does not query advertising accounts,
competitors, keyword volumes, market statistics, model providers, or external
APIs. It does not publish content, activate campaigns, spend funds, or invent
performance forecasts. Planning defaults, targeting, final URLs, consent,
platform policy, and every factual claim require human review.

## Validation

Before approval MENAXVI checks campaign completeness, selected locale, evidence,
budget, selected-channel coverage, and safety boundaries. Approval is blocked
when a required check fails. Retry, rollback, persistence, and evidence ordering
remain part of the dashboard workflow.
