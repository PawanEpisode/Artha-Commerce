import { type InfiniteData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { isPushReceivedMessage } from '~/sw/messages'

import { getInbox, isNotificationsDisabled, postInboxRead } from '../lib/api'
import { markReadInPages } from '../lib/inbox'
import { notificationKeys } from '../lib/keys'
import { INBOX_PAGE_SIZE, INBOX_POLL_MS } from '../lib/limits'
import type { InboxPage, InboxReadTarget } from '../lib/schemas'

/** Polling stops for good once the server says the feature is off for this student (403 `notifications_disabled`). */
const pollWhileOn = (query: { state: { error: unknown } }) =>
  isNotificationsDisabled(query.state.error) ? false : INBOX_POLL_MS

/**
 * The bell's data: the unread count, asked for every 60 seconds while the tab is visible, whenever the window gets
 * focus, and at once when the worker says a push arrived. One item is enough: only the count is used.
 */
export function useBellCount() {
  const enabled = useFeatureFlag('notifications_ui')
  const query = useQuery({
    queryKey: notificationKeys.bell,
    queryFn: () => getInbox({ limit: 1 }),
    enabled,
    refetchInterval: pollWhileOn,
    refetchOnWindowFocus: 'always',
    select: (page: InboxPage) => page.unread_count,
  })
  usePushRefresh(enabled)
  return {
    /** Null until the first answer. */
    unread: query.data ?? null,
    /** The flag is off here, or the server said so: show no bell at all. */
    off: !enabled || isNotificationsDisabled(query.error),
  }
}

/** The worker posts a message after it shows a push: refresh the bell and any open inbox now, not in a minute. */
export function usePushRefresh(enabled: boolean) {
  const qc = useQueryClient()
  useEffect(() => {
    if (!enabled || typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return
    const onMessage = (event: MessageEvent) => {
      if (isPushReceivedMessage(event.data)) void qc.invalidateQueries({ queryKey: notificationKeys.inbox })
    }
    const worker = navigator.serviceWorker
    worker.addEventListener('message', onMessage)
    return () => worker.removeEventListener('message', onMessage)
  }, [enabled, qc])
}

/** The inbox page's list: cursor paged, refreshed on focus and every minute like the bell. */
export function useInboxList() {
  const enabled = useFeatureFlag('notifications_ui')
  return useInfiniteQuery({
    queryKey: notificationKeys.inboxList,
    queryFn: ({ pageParam }) => getInbox({ cursor: pageParam, limit: INBOX_PAGE_SIZE }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled,
    refetchInterval: pollWhileOn,
    refetchOnWindowFocus: 'always',
  })
}

type Cached = InfiniteData<InboxPage, string | null>

/**
 * Marks items read. The list and the bell change at once; a failure puts them back, and the server's count wins when
 * the answer arrives. Idempotent on the server, so a double tap is harmless.
 */
export function useMarkInboxRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (target: InboxReadTarget) => postInboxRead(target),
    onMutate: async (target) => {
      await qc.cancelQueries({ queryKey: notificationKeys.inbox })
      const list = qc.getQueryData<Cached>(notificationKeys.inboxList)
      const bell = qc.getQueryData<InboxPage>(notificationKeys.bell)
      if (list) qc.setQueryData<Cached>(notificationKeys.inboxList, markReadInPages(list, target))
      if (bell) {
        const optimistic = list ? (markReadInPages(list, target).pages[0]?.unread_count ?? 0) : bell.unread_count
        qc.setQueryData<InboxPage>(notificationKeys.bell, { ...bell, unread_count: 'all' in target ? 0 : optimistic })
      }
      return { list, bell }
    },
    onError: (_error, _target, context) => {
      if (context?.list) qc.setQueryData(notificationKeys.inboxList, context.list)
      if (context?.bell) qc.setQueryData(notificationKeys.bell, context.bell)
    },
    onSuccess: (unread) => {
      qc.setQueryData<InboxPage>(notificationKeys.bell, (old) => (old ? { ...old, unread_count: unread } : old))
    },
    onSettled: () => qc.invalidateQueries({ queryKey: notificationKeys.inbox }),
  })
}
