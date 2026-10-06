import { Badge, Button, Check, LoaderCircle } from '@artha/design-system'
import type { MouseEvent } from 'react'

import { followableLink, formatSent } from '../lib/inbox'
import type { InboxItem } from '../lib/schemas'

/**
 * The inbox: one row per notification, newest first. Unread rows say "New" in words and are set in bold, and the
 * unread dot is decoration only. The title is the way in (a link, so it can open in a new tab); the check button marks
 * one read without opening it. Props only: the container owns data, navigation and analytics.
 */
export function InboxList({
  items,
  now,
  hasMore,
  loadingMore,
  onOpen,
  onMarkRead,
  onLoadMore,
}: {
  items: readonly InboxItem[]
  /** Milliseconds since the epoch used for the "5 min ago" text. */
  now: number
  hasMore: boolean
  loadingMore: boolean
  onOpen: (item: InboxItem, event: MouseEvent<HTMLElement>) => void
  onMarkRead: (item: InboxItem) => void
  onLoadMore: () => void
}) {
  return (
    <div className="space-y-4">
      <ul className="divide-y overflow-hidden rounded-2xl border bg-card">
        {items.map((item) => {
          const link = followableLink(item)
          const titleClass = `rounded-sm text-base break-words outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 ${
            item.read ? 'font-medium' : 'font-bold'
          }`
          return (
            <li
              key={item.id}
              className={`flex items-start gap-2 p-4 ${item.read ? '' : 'border-l-4 border-l-primary'}`}
            >
              <div className="min-w-0 flex-1 space-y-1">
                <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">{item.category_label}</Badge>
                  {item.read ? <span className="sr-only">Read</span> : <Badge variant="accent">New</Badge>}
                  <time dateTime={item.created_at}>{formatSent(item.created_at, now)}</time>
                </p>
                <h2 className="min-w-0">
                  {link ? (
                    <a href={link} className={`${titleClass} hover:underline`} onClick={(event) => onOpen(item, event)}>
                      {item.title}
                    </a>
                  ) : (
                    <button
                      type="button"
                      className={`${titleClass} text-left`}
                      onClick={(event) => onOpen(item, event)}
                    >
                      {item.title}
                    </button>
                  )}
                </h2>
                <p className="text-sm break-words text-muted-foreground">{item.body}</p>
              </div>
              {item.read ? null : (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-11 shrink-0"
                  aria-label={`Mark "${item.title}" as read`}
                  onClick={() => onMarkRead(item)}
                >
                  <Check aria-hidden />
                </Button>
              )}
            </li>
          )
        })}
      </ul>
      {hasMore ? (
        <div className="flex justify-center">
          <Button variant="outline" onClick={onLoadMore} disabled={loadingMore} aria-busy={loadingMore}>
            {loadingMore ? <LoaderCircle aria-hidden className="animate-spin motion-reduce:animate-none" /> : null}
            {loadingMore ? 'Loading…' : 'Show older'}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
