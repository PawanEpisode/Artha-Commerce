---
name: django-backend-layers
description: Use for any work in apps/api. Layered Django architecture, module layout, Supabase auth, migrations, RLS, testing and serverless constraints.
---

# Django backend layers

## Module layout (`apps/api/modules/<name>/`)

```
models.py        tables only; no business rules beyond constraints
selectors.py     READ queries, return model instances/querysets, no side effects
services.py      WRITE operations and business rules, transactional (`@transaction.atomic`)
serializers.py   DRF input validation and output shape
views.py         thin: auth, parse, call service/selector, serialise
urls.py          routes, included from config/urls.py under /api/v1/
tests/           pytest, one file per endpoint group
```

Dependency direction: `views -> services/selectors -> models`. Views never touch the ORM. Services never import views or serializers. Cross-module calls go through the other module's `services`/`selectors`, never its models in write paths.

## Rules

- **Stateless.** No sessions, no local files, no in-process state that must survive a request (Vercel runs many short-lived instances).
- **Auth.** `core.authentication.SupabaseJWTAuthentication` verifies the Supabase JWT (JWKS for asymmetric keys, HS256 secret for legacy). `request.user` is a `SupabaseUser`; its `id` is the Supabase user UUID. Scope every query by `request.user.id`. Default permission is `IsAuthenticated`; public endpoints opt out explicitly.
- **Schema ownership.** Django migrations own the `public` schema. Supabase owns `auth` and `storage`. Reference `auth.users` by UUID value (no cross-schema FK) to keep migrations portable.
- **RLS.** `core.apps.enable_rls_everywhere` enables RLS on all public tables after each migrate so the Supabase Data API can never read them. Keep the Data API disabled in Supabase.
- **Idempotency and safety.** Make writes safe to retry. Use `get_or_create`/unique constraints instead of check-then-insert.
- **Errors.** Raise DRF exceptions; the handler formats `{"error": {code, message, details}}`.
- **Pagination.** Lists use `core.pagination.DefaultPagination`. No unbounded querysets in responses. Use `select_related`/`prefetch_related`.
- **Database connections.** Runtime `DATABASE_URL` is the transaction pooler (6543); `migrate` uses `DIRECT_DATABASE_URL`. Server-side cursors are disabled; do not rely on session state (temp tables, `SET`).
- **Time budget.** Requests must finish well under the 30s function limit. Slow or batch work (bulk AI generation, imports) belongs in a queue/cron (Supabase `pg_cron`/Edge Function or Vercel Cron) not in a request.
- **AI.** Only `integrations/gemini.py` talks to Gemini. Services call it; views never do. Cap input size, set timeouts, never log prompts with personal data.
- **Config.** All settings from env in `config/settings.py`. Document new vars in `.env.example` and `docs/SETUP.md`.

## Adding an endpoint

1. Model + `python manage.py makemigrations <app>` (review the SQL: `sqlmigrate`)
2. selector/service, serializer, view, url
3. Tests: unauthenticated 401, happy path, validation 400, cannot access another user's data
4. `ruff check . && ruff format . && pytest`

## Scaling notes

Horizontal scale comes from statelessness plus the pooler. Add read-heavy caching with Postgres materialised views or Vercel/CDN cache headers on public GETs. Move to a dedicated worker (Fly/Railway/Supabase Edge) only when background jobs outgrow cron.
