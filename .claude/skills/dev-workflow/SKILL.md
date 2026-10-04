---
name: dev-workflow
description: Use for any git, commit, branch, PR or tooling question. Explains hooks, Conventional Commits, lint/format commands and the checks that must pass.
---

# Developer workflow

## Daily commands

```bash
pnpm dev:web            # app on :3000
pnpm check              # typecheck + eslint + prettier check + tests + build (run before a PR)
pnpm lint:fix           # auto-fix ESLint (also sorts imports, removes unused imports)
pnpm format             # Prettier (also sorts Tailwind classes)
pnpm lint:api           # ruff check + format check (Python)
pnpm test:web / test:api
```

## Branches and commits

- Branch from `main`: `feat/syllabus-tracker`, `fix/login-redirect`, `docs/prd-time-tracker`.
- **Conventional Commits** are enforced by commitlint: `type(scope): subject`
  - types: `feat fix docs style refactor perf test build ci chore revert`
  - scopes: `web api ds docs ci deps db product tooling`
  - examples: `feat(web): add coverage ring`, `fix(api): scope profile query by user`, `docs(product): add F-02 PRD`
- Small commits, one concern each. Imperative subject, no trailing period, max 100 chars.

## Hooks (installed by `pnpm install` via Husky)

| Hook | Runs | If it fails |
| --- | --- | --- |
| pre-commit | lint-staged: ESLint --fix, Prettier, ruff on staged files | fix what it reports and commit again |
| commit-msg | commitlint | reword the message |
| pre-push | typecheck + web tests | fix types or tests |

Do not use `--no-verify`. If a hook is wrong, fix the hook in a separate PR.

## Pull requests

- Title follows Conventional Commits (it becomes the squash commit).
- Fill the PR template. CI (web, api, secrets scan) must be green. Squash merge.
- UI changes include screenshots at mobile and desktop widths.
- Dependabot PRs: merge after CI is green; read the changelog for majors.

## Lint rules worth knowing

- Imports are auto-sorted; unused imports are errors.
- `no-console` warns (use `console.warn/error` only, or Sentry).
- No `any`; avoid `!` non-null assertions.
- Cross-module imports only through barrels; modules never import from `routes`; UI only from `@artha/design-system`.
- Warnings fail CI (`--max-warnings=0`).
