import type { LinkProps } from '@tanstack/react-router'

export interface SectionLink {
  value: string
  label: string
  to: LinkProps['to'] & string
}

/** The section whose path is the longest prefix of `pathname`, so `/app/tracker/day/x` still lights up Today. */
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

/** Sections of the tracker area (the focus timer and both settings pages are part of it). */
export const TRACKER_SECTIONS: ReadonlyArray<SectionLink> = [
  { value: 'today', label: 'Today', to: '/app/tracker' },
  { value: 'reports', label: 'Reports', to: '/app/tracker/reports' },
  { value: 'log', label: 'Log', to: '/app/tracker/log' },
  { value: 'goals', label: 'Goals', to: '/app/tracker/goals' },
  { value: 'focus', label: 'Focus timer', to: '/app/focus' },
  { value: 'settings', label: 'Settings', to: '/app/settings/tracker' },
]
