# ArthaCommerce

Exam preparation workspace for CA, CS and CMA students in India. Public marketing and feature pages are indexable and
shareable (WhatsApp previews); signed-in students get a workspace that stores their plan, progress and notes.

## Stack

| Layer | Choice |
| --- | --- |
| Web | TanStack Start (React 19, SSR), TanStack Router + Query, Tailwind CSS v4, shadcn/ui (Radix), `motion` (Framer Motion) |
| API | Django 5.2 LTS + Django REST Framework, stateless, Supabase JWT auth |
| Data/Auth/Storage | Supabase (Postgres, Auth, Storage, Realtime). Django is the only writer of app data |
| AI | Google AI Studio (Gemini), called only from the API |
| Observability | Sentry (web + api), PostHog (web, proxied via `/ingest`) |
| Hosting | Vercel: two projects from one monorepo (`apps/web`, `apps/api`) |

## Repo map

- `apps/web`: frontend. `src/routes` (thin), `src/modules/*` (features), `src/design-system` (tokens, layout, motion), `src/components/ui` (shadcn primitives), `src/lib` (env, supabase, api)
- `apps/api`: backend. `config` (settings, urls), `core` (auth, errors, health), `modules/*` (domain apps), `integrations/*` (Gemini)
- `docs`: `ARCHITECTURE.md`, `SETUP.md` (platform steps and env vars)
- `.claude/skills`: task playbooks. Read the relevant one before starting work.

## Commands

```bash
pnpm install
pnpm dev:web                 # http://localhost:3000
pnpm typecheck && pnpm lint && pnpm test:web && pnpm build:web
cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
python manage.py migrate && python manage.py runserver 8000
pytest && ruff check .
```

## Non-negotiable rules

1. **Modular.** Every feature or issue is a self-contained module (`src/modules/<name>` on web, `modules/<name>` on api) with a public `index.ts` barrel. Import other modules only through their barrel.
2. **Separation of concerns.** Web: routes -> containers (state, data) -> presentational components (props only). API: views -> services (writes) -> selectors (reads) -> models. Business logic never lives in views or JSX.
3. **DRY.** Reuse before creating. Shared UI goes in `components/ui` or `design-system`; shared data (courses, features) lives once in `modules/catalog`.
4. **Design system only.** No raw hex or arbitrary colours. Use semantic tokens (`bg-primary`, `text-muted-foreground`). Compose from `components/ui`. Details: `.claude/skills/design-system-usage`.
5. **URL-driven.** Every screen and meaningful state has a URL. Public pages set SEO via `buildHead()`. Private pages use `noindex`.
6. **Secrets.** Only `VITE_*` values reach the browser, and only public ones. Gemini and service keys exist only on the API. Never commit `.env*`.
7. **Types and validation at the edges.** Zod/typed env on web, DRF serializers on api.
8. **Tests.** Pure logic and every API endpoint get tests. Run typecheck, lint, build and pytest before declaring done.

## Workflow for any task

Follow `.claude/skills/new-feature-module`. Keep changes small and reviewable, one concern per PR.

## Product status

First milestone shipped: foundation, design system, SEO, public pages, auth wiring, API skeleton.
The feature set in `modules/catalog/features.ts` is provisional pending the product feature screenshots.
