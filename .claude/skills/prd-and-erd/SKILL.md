---
name: prd-and-erd
description: Use when starting a main product pointer (F-xx in docs/product/FEATURE_MAP.md). How to write the PRD and ERD before building, and how they connect to modules.
---

# Writing a PRD and ERD for a main pointer

One main pointer at a time, in the order agreed in `docs/product/FEATURE_MAP.md` section 8.

1. **Read the pointer** in `FEATURE_MAP.md`. `[NOTE]` items are requirements from the founder; `[ADD]` items are proposals to accept, change or drop. Resolve every `[?]`.
2. **Copy templates**: `docs/templates/PRD_TEMPLATE.md` to `docs/product/prd/F-xx-<name>.md`, `ERD_TEMPLATE.md` to `docs/product/erd/F-xx-<name>.md`.
3. **PRD first**: problem, users, success metrics (with PostHog event names), scope (in / out), flows (Mermaid), numbered requirements with acceptance criteria, screens with their URLs, API surface, notifications, non-functional needs, risks.
4. **ERD second**: Mermaid `erDiagram`, a table per entity (type, null, default, notes), keys and indexes driven by the real query patterns, storage buckets, RLS stance, migration order. Reuse the taxonomy tables; never duplicate course/subject/chapter data.
5. **Check against the rules**: every entity belongs to one Django module; user data is scoped by the Supabase user id; files go to Supabase Storage with signed URLs; AI usage has quotas.
6. **Review with the founder**, mark Status "Approved", then slice into PR-sized issues (use `new-feature-module`).
7. Keep PRD and ERD updated when behaviour changes; they are the source of truth, not chat history.
