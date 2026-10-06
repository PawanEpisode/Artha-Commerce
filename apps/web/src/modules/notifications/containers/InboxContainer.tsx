import { Alert, Bell, Button, Container, EmptyState, ListChecks, Settings, Skeleton } from '@artha/design-system'
import { Link, useRouter } from '@tanstack/react-router'
import type { MouseEvent } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { InboxList } from '../components/InboxList'
import { NotificationsOff } from '../components/NotificationsOff'
import { useInboxList, useMarkInboxRead } from '../hooks/useInbox'
import { notificationAnalytics } from '../lib/analytics'
import { isNotificationsDisabled } from '../lib/api'
import { flattenInbox, followableLink, isModifiedClick, secondsSince, unreadPhrase } from '../lib/inbox'
import type { InboxItem } from '../lib/schemas'

/**
 * `/app/notifications`: the inbox. Opening an item marks it read and follows its link (only an allow-listed relative
 * path; anything else just marks it read). Behind the `notifications_ui` flag; the rest of the app is untouched when
 * it is off. The one `h1` is always "Inbox".
 */
export function InboxContainer() {
  const router = useRouter()
  const flagOn = useFeatureFlag('notifications_ui')
  const list = useInboxList()
  const markRead = useMarkInboxRead()

  const off = !flagOn || isNotificationsDisabled(list.error)
  const items = flattenInbox(list.data)
  const unread = list.data?.pages[0]?.unread_count ?? null

  const open = (item: InboxItem, event: MouseEvent<HTMLElement>) => {
    const link = followableLink(item)
    notificationAnalytics.inboxOpened({
      category: item.category,
      seconds_since_sent: secondsSince(item.created_at, Date.now()),
    })
    if (!item.read) markRead.mutate({ ids: [item.id] })
    if (!link) return
    if (isModifiedClick(event)) return // the browser opens it elsewhere; the item is read either way
    event.preventDefault()
    router.history.push(link)
  }

  return (
    <Container className="max-w-3xl space-y-6 py-8 sm:py-12">
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <h1 className="text-3xl font-extrabold">Inbox</h1>
            {off ? null : (
              <p className="text-muted-foreground">Everything Artha has told you lately, in case you missed a push.</p>
            )}
          </div>
          {off ? null : (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                onClick={() => markRead.mutate({ all: true })}
                disabled={!unread || markRead.isPending}
              >
                <ListChecks aria-hidden /> Mark all as read
              </Button>
              <Button variant="ghost" asChild>
                <Link to="/app/settings/notifications">
                  <Settings aria-hidden /> Settings
                </Link>
              </Button>
            </div>
          )}
        </div>
        {off ? null : (
          <p role="status" aria-live="polite" className="text-sm font-semibold">
            {unread === null ? '' : unreadPhrase(unread)}
          </p>
        )}
      </header>

      {off ? (
        <NotificationsOff />
      ) : list.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span className="sr-only" role="status">
            Loading your notifications…
          </span>
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : list.isError ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            We could not load your notifications.
            <Button variant="outline" onClick={() => void list.refetch()}>
              Try again
            </Button>
          </span>
        </Alert>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Bell aria-hidden />}
          title="Nothing here yet"
          description="When Artha sends you an alert, it is listed here too. Alerts you switch off for the inbox in settings are not shown."
        />
      ) : (
        <>
          {markRead.isError ? <Alert variant="error">We could not mark that as read. Please try again.</Alert> : null}
          <InboxList
            items={items}
            now={list.dataUpdatedAt || Date.now()}
            hasMore={list.hasNextPage}
            loadingMore={list.isFetchingNextPage}
            onOpen={open}
            onMarkRead={(item) => markRead.mutate({ ids: [item.id] })}
            onLoadMore={() => void list.fetchNextPage()}
          />
        </>
      )}
    </Container>
  )
}
