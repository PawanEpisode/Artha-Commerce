---
name: clean-code-review
description: Use before finishing or reviewing any change. Checklist for DRY, separation of concerns, naming, complexity and review hygiene.
---

# Clean code review

Run this on your own diff before asking for review.

## Structure

- Does each file have one reason to change? Split files over ~200 lines or doing two jobs.
- Is logic separated from presentation (JSX/serializers/views) and from IO (API calls, DB)?
- Could a pure function replace a block of component or view logic? Extract and unit test it.

## DRY (without over-abstracting)

- Same literal, class string, query or validation in 3 places -> extract. Two places -> consider. Different reasons to change -> leave.
- Static content (courses, features, FAQ) lives once in `modules/catalog` or the module's `data/`.
- Prefer a variant on an existing primitive over a new near-duplicate component.

## Naming and readability

- Names state intent (`buildPlan`, `get_or_create_profile`), no `data2`, `temp`, `util`.
- Functions do one thing, ~20 lines, at most 3 params (else pass an object).
- Early returns over nested conditionals. No dead code or commented-out blocks.
- Comments explain why, not what.

## Safety

- No secrets, tokens, PII in code, logs or analytics payloads.
- Inputs validated at the boundary (zod / DRF serializers). Queries scoped to the user.
- Errors surfaced to the user in plain words and to Sentry with context.

## Performance and UX

- No request waterfalls; fetch in parallel. Lists paginated.
- Loading, empty and error states exist. No layout shift.

## PR hygiene

- One concern per PR, title in imperative mood, description says what and why.
- Screenshots for UI. Migration called out. Env var changes called out.
