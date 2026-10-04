# Contributing

## Setup

```bash
corepack enable
pnpm install        # also installs the git hooks (Husky)
pnpm dev:web
```

Python (API): see `docs/SETUP.md` section 9.

## Before you push

```bash
pnpm check          # typecheck, eslint, prettier check, tests, build
pnpm lint:api && pnpm test:api
```

Hooks run most of this automatically on commit and push.

## Commits

Conventional Commits: `type(scope): subject`. Examples: `feat(web): add coverage ring`, `fix(api): scope query by user`, `docs(product): add F-02 PRD`.
Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
Scopes: web, api, ds, docs, ci, deps, db, product, tooling.

## Where things go

See `CLAUDE.md` (rules and repo map) and `.claude/skills/*` (playbooks): `new-feature-module`, `frontend-architecture`, `design-system-usage`, `django-backend-layers`, `seo-and-sharing`, `clean-code-review`, `ux-aha-moments`, `dev-workflow`, `prd-and-erd`.

## Pull requests

One concern per PR, Conventional Commit title, template filled, CI green, squash merge.
