# ArthaCommerce

Exam preparation workspace for CA, CS and CMA students in India.

- **Web**: TanStack Start, Tailwind v4, shadcn/ui, Motion: `apps/web`
- **API**: Django + DRF on Supabase Postgres: `apps/api`
- **Docs**: [Setup per platform and env vars](docs/SETUP.md) · [Architecture](docs/ARCHITECTURE.md) · [Engineering rules](CLAUDE.md)
- **Skills/playbooks**: `.claude/skills/*`

Quick start:

```bash
corepack enable && pnpm install
cp apps/web/.env.example apps/web/.env.local
pnpm dev:web
```

The site works without any keys (auth, analytics and error reporting switch on when env vars are present).
