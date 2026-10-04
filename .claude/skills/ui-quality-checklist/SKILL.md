---
name: ui-quality-checklist
description: Use whenever a UI component, screen or style is created or changed. Forces a pass over all four themes (Reading, Light, Dark, System), UI design, WCAG 2.2 AA accessibility and responsiveness on every device width.
---

# UI quality checklist

Run this on every component or screen you create or change, however small. Do not mark UI work done until each section is ticked.

## 1. Themes (all four)

ArthaCommerce has four theme preferences, stored in localStorage key `theme`:

| Preference | Behaviour |
| --- | --- |
| `reading` | **Default.** Warm paper background, serif long-form text. Applied as `data-theme="reading"` |
| `light` | Cool neutral light |
| `dark` | Dark. Sets `data-theme="dark"` and the `.dark` class |
| `system` | Stored as `system`. Resolves by device-local time: 06:00 to 18:00 light, 18:00 to 06:00 dark. Re-evaluated at the boundaries |

- [ ] Colours come from semantic tokens only (`bg-background`, `text-foreground`, `border-border`, `bg-primary`). No hex, `rgb()`, `dark:` colour overrides or palette classes (`bg-indigo-500`)
- [ ] If you need a new colour, add a token for all three palettes (`reading`, `light`, `dark`) in `packages/design-system/src/styles.css`, then run `pnpm check:contrast`
- [ ] Anything that must differ per theme uses the `reading:` / `dark:` variants sparingly; prefer tokens
- [ ] Long-form text (guides, notes, explanations) uses `prose-reading`
- [ ] Images, SVGs and shadows look right on all three palettes (no white boxes on dark, no invisible borders on reading)
- [ ] Never read the theme in JS to pick colours. Use `useTheme()` only for the switcher
- [ ] Email templates use hex values from the tokens (`packages/email-templates`); run `pnpm emails:build`

## 2. UI design

- [ ] Built from `@artha/design-system` primitives; checked the showcase before making anything new
- [ ] Clear hierarchy: one primary action per view, consistent spacing scale, `rounded-lg/xl/2xl`
- [ ] Loading, empty, error and success states exist and look designed
- [ ] Motion explains change (150 to 600 ms) and is skipped under `prefers-reduced-motion`
- [ ] Icons only from `@artha/design-system` (curated `icons.ts`, Lucide). Never import `lucide-react` directly (ESLint blocks it). Add a new icon to `icons.ts` first. Decorative icons get `aria-hidden`; icon-only buttons get an `aria-label`
- [ ] New or changed primitive has an entry in `/design-system` (`DesignShowcase`)

## 3. Accessibility (WCAG 2.2 AA)

- [ ] Contrast: body text 7:1, UI text 4.5:1, borders of inputs and focus rings 3:1 in every theme (`pnpm check:contrast` must pass)
- [ ] Visible `focus-visible` ring; full keyboard path; logical tab order; no keyboard traps
- [ ] Touch targets at least 44 x 44 px on mobile
- [ ] Every control has a label (`Label` / `TextField`); errors use `aria-invalid` and `aria-describedby`; live results use `aria-live`
- [ ] Colour is never the only signal (add icon or text for status)
- [ ] Semantic HTML first (`button`, `a`, `nav`, `main`, headings in order); ARIA only to fill gaps
- [ ] Menus, dialogs, radio groups and tabs use the Radix-based primitives so focus and arrow keys work
- [ ] Text can be zoomed to 200% without loss; do not disable zoom

## 4. Responsive on every device

Check at **320, 390, 768, 1280 px** (and 1920 if the layout is wide).

- [ ] No horizontal page scroll at 320 px
- [ ] Mobile first: base classes are mobile, add `sm: md: lg:` upward
- [ ] Long words, emails and URLs wrap or truncate (`min-w-0`, `break-words`)
- [ ] Tables and wide content scroll inside their own container, not the page
- [ ] Header, menus and dialogs usable one-handed on a phone; safe-area padding where fixed to edges
- [ ] Tap and hover: nothing essential only on hover
- [ ] Landscape phones and large desktops look intentional (max-width on reading text, about 68ch)

## 5. Verify

1. `pnpm check:contrast` and `pnpm check` (typecheck, lint, format, tests, build)
2. Open the page and switch through Reading, Light, Dark and System at 320, 390, 768 and 1280 px
3. Tab through it with the keyboard only
4. Mention in the PR which themes and widths you checked, with screenshots
