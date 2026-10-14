# Auditable Operations Agent

## Product problem

Enterprise operations teams need answers that connect customer context with recent evidence. A useful assistant must also show where each claim came from, keep customers isolated and stop before a high-impact action is taken.

## My contribution

I helped build and verify a local POC that converts an enterprise question into reviewable candidates:

1. classify the question and allowed scope;
2. retrieve authorized records and keep source evidence;
3. match verified content to the customer's context;
4. produce content, profile, lead or outreach candidates;
5. apply quality and risk gates;
6. require a person to approve the deliverable.

The implementation models the workflow explicitly:

```text
RECEIVED → CLASSIFIED → RETRIEVING → EVIDENCE_READY
         → ANALYZING → REVIEW_REQUIRED → APPROVED → DELIVERED

Exceptional outcomes: BLOCKED / FAILED
```

## Engineering decisions

- **Evidence before recommendation.** Important outputs retain links to the source records used.
- **Human authority.** The system proposes; it does not autonomously send email, publish content or change subscriptions.
- **Customer isolation.** Context and memory are scoped to one customer.
- **Selective memory.** Only approved, useful facts are recalled; retention work supports preview before cleanup.
- **Honest scoring.** A 0–100 lead score ranks candidates. It is not described as conversion probability.
- **Test fallback.** The application path supports PostgreSQL, while isolated tests may use SQLite.

## Verification

The current local POC passes **77 automated tests**. A separate sanitized memory-recall evaluation covered 12 cases. Test coverage includes state transitions, evidence checks, customer boundaries, review gates and failure paths.

## Current limits

- local proof of concept rather than a production service;
- no real enterprise-behavior stream is claimed;
- no unrestricted connection to internal data agents;
- no automatic external action.

These limits are deliberate product boundaries, not hidden capabilities.

