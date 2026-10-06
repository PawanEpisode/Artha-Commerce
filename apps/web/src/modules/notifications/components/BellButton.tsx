import { Bell, Button } from '@artha/design-system'
import type { MouseEvent } from 'react'

import { bellCountLabel, unreadPhrase } from '../lib/inbox'

export const INBOX_PATH = '/app/notifications'

/**
 * The bell in the header: a real link to the inbox with the unread count as text on a badge, so the number (not the
 * colour) carries the meaning. `announcement` is a polite live region for count changes; it is empty on first load.
 */
export function BellButton({
  unread,
  announcement,
  current,
  onOpen,
}: {
  /** Null until the first answer. */
  unread: number | null
  announcement: string | null
  /** The inbox is the page showing. */
  current: boolean
  onOpen: (event: MouseEvent<HTMLAnchorElement>) => void
}) {
  const label = unread === null ? 'Notifications' : `Notifications, ${unreadPhrase(unread).toLowerCase()}`
  const count = unread === null ? '' : bellCountLabel(unread)
  return (
    <div className="relative shrink-0">
      <Button asChild variant="ghost" size="icon" className="size-11 rounded-full">
        <a href={INBOX_PATH} aria-label={label} aria-current={current ? 'page' : undefined} onClick={onOpen}>
          <Bell aria-hidden />
        </a>
      </Button>
      {count ? (
        <span
          aria-hidden
          className="pointer-events-none absolute top-0.5 right-0 grid min-w-5 place-items-center rounded-full border-2 border-background bg-primary px-1 text-[11px] leading-4 font-bold text-primary-foreground tabular-nums"
        >
          {count}
        </span>
      ) : null}
      <span role="status" aria-live="polite" className="sr-only">
        {announcement}
      </span>
    </div>
  )
}
