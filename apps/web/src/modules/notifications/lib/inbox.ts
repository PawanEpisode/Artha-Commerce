import { isAllowedDeepLink } from '~/sw/deeplink'

import { BELL_COUNT_MAX } from './limits'
import type { InboxItem, InboxPage, InboxReadTarget } from './schemas'

/** The bell's text: the count, "99+" beyond the cap, and nothing at zero. */
export const bellCountLabel = (unread: number): string =>
  unread <= 0 ? '' : unread > BELL_COUNT_MAX ? `${BELL_COUNT_MAX}+` : String(unread)

/** What assistive technology hears for the bell button and for a change of the count. */
export const unreadPhrase = (unread: number): string =>
  unread <= 0 ? 'No unread notifications' : unread === 1 ? '1 unread notification' : `${unread} unread notifications`

/**
 * The polite announcement for a count that changed, or null when there is nothing to say: the first answer is silent
 * (the page just loaded), and so is an unchanged count.
 */
export function announceChange(previous: number | null, next: number): string | null {
  if (previous === null || previous === next) return null
  return unreadPhrase(next)
}

/** Whole seconds between sending and `now`, never negative (a clock a little behind must not send -3). */
export function secondsSince(iso: string, now: number): number {
  const sent = Date.parse(iso)
  return Number.isNaN(sent) ? 0 : Math.max(0, Math.round((now - sent) / 1000))
}

/** "just now", "5 min ago", "3 h ago", "yesterday", or the date. Short, because the list is dense on a phone. */
export function formatSent(iso: string, now: number): string {
  const sent = Date.parse(iso)
  if (Number.isNaN(sent)) return ''
  const minutes = Math.floor((now - sent) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(new Date(sent))
}

/** The link to follow for an item, or null when it is not an allowed relative path (the item then only gets marked read). */
export const followableLink = (item: Pick<InboxItem, 'deep_link'>): string | null =>
  isAllowedDeepLink(item.deep_link) ? item.deep_link : null

/** A click that the browser should handle itself (new tab, new window, download): leave it alone. */
export const isModifiedClick = (event: {
  button: number
  metaKey: boolean
  ctrlKey: boolean
  shiftKey: boolean
  altKey: boolean
}): boolean => event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey

export interface InfiniteInbox<P = unknown> {
  pages: InboxPage[]
  pageParams: P[]
}

const covers = (target: InboxReadTarget, id: string) => 'all' in target || target.ids.includes(id)

/** The cached pages with `target` marked read, and the unread count lowered by how many actually changed. */
export function markReadInPages<P>(data: InfiniteInbox<P>, target: InboxReadTarget): InfiniteInbox<P> {
  const changed = new Set<string>()
  const pages = data.pages.map((page) => ({
    ...page,
    results: page.results.map((item) => {
      if (item.read || !covers(target, item.id)) return item
      changed.add(item.id)
      return { ...item, read: true }
    }),
  }))
  const unread = 'all' in target ? 0 : Math.max(0, (data.pages[0]?.unread_count ?? 0) - changed.size)
  return { ...data, pages: pages.map((page) => ({ ...page, unread_count: unread })) }
}

/** Every item across the loaded pages, once, in order (a refetch can briefly return one item on two pages). */
export function flattenInbox(data: InfiniteInbox | undefined): InboxItem[] {
  const seen = new Set<string>()
  const items: InboxItem[] = []
  for (const page of data?.pages ?? []) {
    for (const item of page.results) {
      if (seen.has(item.id)) continue
      seen.add(item.id)
      items.push(item)
    }
  }
  return items
}
