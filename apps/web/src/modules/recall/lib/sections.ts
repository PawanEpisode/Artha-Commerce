import type { LinkProps } from '@tanstack/react-router'

export interface SectionLink {
  value: string
  label: string
  to: LinkProps['to'] & string
}

/** The section whose path is the longest prefix of `pathname`. */
export function activeSection(pathname: string, items: ReadonlyArray<SectionLink>): string | undefined {
  const path = pathname.replace(/\/+$/, '') || '/'
  let best: SectionLink | undefined
  for (const item of items) {
    const base = item.to.replace(/\/+$/, '') || '/'
    const hit = path === base || path.startsWith(`${base}/`)
    if (hit && (!best || base.length > best.to.replace(/\/+$/, '').length)) best = item
  }
  return best?.value
}

/** Sections of the recall area in release 1. Decks and quick revision join in later releases. */
export const RECALL_SECTIONS: ReadonlyArray<SectionLink> = [
  { value: 'today', label: 'Today', to: '/app/recall' },
  { value: 'cards', label: 'Cards', to: '/app/recall/cards' },
  { value: 'forgotten', label: 'Forgotten', to: '/app/recall/forgotten' },
  { value: 'stats', label: 'Stats', to: '/app/recall/stats' },
  { value: 'settings', label: 'Settings', to: '/app/settings/recall' },
]
