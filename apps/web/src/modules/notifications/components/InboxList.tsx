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
    <div className="space-y-3">
      <ul className="divide-y overflow-hidden rounded-lg border bg-card">
        {items.map((item) => {
          const link = followableLink(item)
          const titleClass = `rounded-sm text-[13px] break-words outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 ${
            item.read ? 'font-medium' : 'font-semibold'
          }`
          return (
            <li
              key={item.id}
              className={`flex items-start gap-2 px-3 py-2 ${item.read ? '' : 'border-l-2 border-l-primary bg-primary/5'}`}
            >
              <div className="min-w-0 flex-1 space-y-0.5">
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
                <p className="text-xs break-words text-muted-foreground">{item.body}</p>
              </div>
              <p className="flex shrink-0 flex-col items-end gap-1 text-xs text-muted-foreground sm:flex-row sm:items-center sm:gap-2">
                <Badge variant="outline">{item.category_label}</Badge>
                {item.read ? <span className="sr-only">Read</span> : <Badge variant="accent">New</Badge>}
                <time dateTime={item.created_at} className="tabular-nums">
                  {formatSent(item.created_at, now)}
                </time>
              </p>
              {item.read ? (
                <span aria-hidden className="size-7 shrink-0 pointer-coarse:size-10" />
              ) : (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="shrink-0"
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
          <Button variant="outline" size="sm" onClick={onLoadMore} disabled={loadingMore} aria-busy={loadingMore}>
            {loadingMore ? <LoaderCircle aria-hidden className="animate-spin motion-reduce:animate-none" /> : null}
            {loadingMore ? 'Loading…' : 'Show older'}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
