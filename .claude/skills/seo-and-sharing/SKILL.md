---
name: seo-and-sharing
description: Use when adding or changing any public page, route, or link preview. Covers buildHead, Open Graph for WhatsApp, JSON-LD, sitemap and indexing rules.
---

# SEO and link previews

Every public page must render its metadata on the server (TanStack Start does this from `head`).

## Per public route

```ts
export const Route = createFileRoute('/features/$slug')({
  head: ({ loaderData }) => buildHead({ title, description, path, jsonLd }),
})
```

`buildHead` (in `~/modules/seo`) emits title, description, canonical, Open Graph, Twitter card and optional JSON-LD.

## Rules

- **One H1** per page, descriptive. Titles under ~60 chars, descriptions 110-160 chars.
- **WhatsApp/LinkedIn/X previews** need absolute `og:image` URLs, 1200x630 PNG/JPG under 300KB, plus `og:title`, `og:description`, `og:url`. `buildHead` handles these; the default image is `public/og/default.png` (regenerate with `pnpm --filter @artha/web og`). Set `VITE_SITE_URL` to the real domain or previews will point at localhost.
- **Per-page image** (courses, features): pass `image` to `buildHead`. Add a generator per type when needed.
- **Canonical** always the clean URL, no query string.
- **Sitemap.** `modules/seo/sitemap.ts` derives paths from `modules/catalog`. A new public route outside the catalog must be added there.
- **Private pages** (`/login`, `/auth/*`, `/app*`) pass `noindex: true` and are disallowed in `robots.txt`.
- **Structured data.** Landing: Organization, WebSite, FAQPage. Detail pages: BreadcrumbList. Add `Course` schema when real course data exists.
- **URLs are the API of the UI.** Human-readable, lowercase, hyphenated, stable. Unknown slugs throw `notFound()`.
- **Performance** is SEO: no layout shift, images sized, fonts via fontsource (self-hosted), minimal client JS on public pages.

## Verify

1. `curl -s <url> | grep -a 'og:'` shows tags in the server HTML.
2. Facebook Sharing Debugger (also refreshes WhatsApp cache) and opengraph.xyz.
3. Google Rich Results Test for JSON-LD.
