# UI redesign: the compact app shell

Direction: a tool, not a brochure (Linear is the reference). Dense, quiet, fast to move around, uses the full width.
This is the contract every `/app` screen follows. Public marketing pages keep their editorial feel but use the same
compact primitives and a slimmer header.

## 1. Shell anatomy (`apps/web/src/modules/layout`, `packages/design-system/src/components/ui/sidebar.tsx`)

```
┌────────┬──────────────────────────────────────────────┐
│ rail   │ topbar 44px: breadcrumb · search (⌘K) · bell  │
│ 232px  ├──────────────────────────────────────────────┤
│ or 48  │ page: full width, 16/24px gutters             │
└────────┴──────────────────────────────────────────────┘
```

- Rendered once by the `/app` layout route (`AppShell`). `staticData: { chrome: 'app' }` tells the root shell to skip the public header.
  A `chrome: 'bare'` child (pop-out timer, PDF reader) gets no frame. `/app/onboarding` hides the rail.
- **Rail**: pinned open (232px) or collapsed (48px, icons). The choice is saved in localStorage and mirrored on `<html data-sidebar>`
  before paint. Collapsed + hover or keyboard focus: the rail opens as an overlay, the page does not move. Click a link, press
  Escape or leave: it closes. `[` toggles. Under 768px it is a left drawer opened from the topbar.
- Groups: Home, Plan (Today, Study plan, Focus, Tracker, Coverage), Learn (Notes, Revision), Practice (Questions, Past papers, MCQ Bank),
  footer: Settings and the account menu (theme, sign out). Links respect the same feature flags as before (`useWorkspaceNav`).
- **Jump-to** (Cmd/Ctrl+K): every destination, settings page, theme and sign out.
- **Settings** is one area (`SettingsFrame`): a side list of all settings pages, so moving between them is one click.
- `Container` and `Page` read `useAppFrame()`: inside the frame they are full width, left aligned, 16/24px gutters, and ignore
  vertical padding classes. An explicit `max-w-*` is kept, left aligned.
- Sticky bars (`SectionTabs`) stick under the topbar through `--site-header-height` (2.75rem in the app, 3rem on public pages).

## 2. Tokens and density (`packages/design-system/src/styles.css`)

| Thing | Before | Now |
| --- | --- | --- |
| Body in the app | 16px | 13px (`[data-app-frame]`), public pages 16px |
| Font | Plus Jakarta (headings) + Inter | Inter only |
| Radius | 14px base, cards 20px | 8px base: `rounded-md` 6 (controls), `rounded-lg` 8 (cards, menus), `rounded-xl` 10 (dialogs) |
| Shadows | large soft glow | 1px hairline (`shadow-soft`), `shadow-lift` only for floating layers |
| Button | 44px (36 from `sm`) | `xs` 24, `sm` 28, default 32, `icon` 32, `icon-sm` 28. `pointer-coarse:` restores 40 to 44px on touch |
| Input / Select | 44px | 32px (44 on touch, 16px text so iOS does not zoom) |
| Badge | pill, 12px, px-3 | `rounded-md`, 11px, px-1.5 |
| Card padding | 24px | 16px (`CardHeader`, `CardContent`) |
| Tabs / SectionTabs | 44px pills, filled primary | 28px segmented, quiet active fill |
| Menus | 44px items | 32px items |

New tokens: `--sidebar`, `--sidebar-accent` (all three palettes, contrast-checked). New primitives: `Sidebar*`, `CommandPalette`,
`DataTable` (+ `TableHeader/Body/Row/Head/Cell/Toolbar`), `Page`, `PageHeader`.

## 3. Page recipes

1. **Every page** = `<Page>` (or the existing `Container`) containing one `<PageHeader title description actions />`, then content.
   No hand-built `<h1>` with `text-2xl/3xl`. Page title is 18px semibold; section titles are 14px semibold.
2. **A list of like things is a table, not a stack of cards.** Questions, past papers, MCQ sets, notes, cards, sessions, notifications,
   history: `DataTable`, 36px rows, the first cell is the link, meta columns muted, numbers `tabular-nums text-right`,
   status as `Badge`. Hide low-priority columns on small screens with `hidden md:table-cell`. The table scrolls inside its own
   wrapper, never the page. Loading = skeleton rows. Empty = `EmptyState` (compact). Keep "load more" below.
3. **Filters** live in one toolbar row above the table (`TableToolbar`): search, selects (compact), then active `FilterChip`s and Clear.
   Filter state stays in the URL.
4. **Dashboards**: a dense grid (`grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4`), cards with `p-4`, one stat row at top
   using `StatTile`. No giant empty hero.
5. **Detail pages**: two columns from `lg`: content on the left (reading width for prose), a 20 to 22rem rail on the right
   for meta and actions. One column on mobile.
6. **Forms and settings**: `<Page width="form">`. Group into one `Card` with `divide-y` rows (label and hint left, control right).
7. **Sub-navigation** inside a module stays `SectionTabs` (now compact).
8. Actions: one primary `Button` (default size) per page header. Toolbar and row actions use `size="sm"` or `icon-sm` ghost.
   No `lg` or `xl` buttons and no `fullWidth` inside the app except a phone form submit.

## 4. Rules

- Tokens only. Fix raw palette classes you meet (`text-emerald-700`, `fill-amber-500`, `dark:text-...`): use `text-success-fg`,
  `text-destructive`, `fill-warning`, `bg-warning-bg` and so on.
- No `rounded-2xl/3xl`, no `shadow-lift` on in-page cards, no `font-bold` headings, no `py-8` or larger on app pages.
- Pills (`rounded-full`) only for avatars, dots and count bubbles.
- Question stems and answer options use the sans UI font (not `prose-reading`). Long notes keep `prose-reading`.
- Keep every behaviour, flag, analytics event, route, test id and accessible name. Update a test only when the markup it pins changed.
- Every change must still pass the four-theme, 320 to 1280px, keyboard and WCAG 2.2 AA checks in `ui-quality-checklist`.

## 5. Verify (from the repo root)

```bash
cd apps/web && npx tsc --noEmit
npx eslint <changed paths> --max-warnings=0 --fix
npx prettier --write <changed paths>
pnpm check:contrast     # after any token change
pnpm check              # full gate, run on your machine
```
