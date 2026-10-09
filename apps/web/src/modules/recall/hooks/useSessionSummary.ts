import { useQuery } from '@tanstack/react-query'

import { recallApi } from '../lib/api'
import { eventStore, type LocalSummary } from '../lib/eventStore'
import { recallKeys } from '../lib/keys'
import type { SessionSummary } from '../lib/schemas'
import { useOnlineStatus, useRecallUser } from './useRecallBasics'

export interface SummaryView {
  reviewed: number
  newCards: number
  ratings: { again: number; hard: number; good: number; easy: number }
  activeSeconds: number
  streakAfter?: number
}

const fromServer = (s: SessionSummary): SummaryView => ({
  reviewed: s.reviewed,
  newCards: s.new,
  ratings: s.ratings,
  activeSeconds: s.active_seconds,
  streakAfter: s.streak_after,
})
const fromLocal = (s: LocalSummary): SummaryView => ({
  reviewed: s.reviewed,
  newCards: s.newCards,
  ratings: s.ratings,
  activeSeconds: s.activeSeconds,
})

/**
 * The summary of a finished session. The server's version (it knows the streak) when it can be reached and has the reviews;
 * otherwise the one kept on this device. Closing a session twice is harmless: the server returns the same summary.
 */
export function useSessionSummary(sessionId: string, synced: boolean) {
  const userId = useRecallUser()
  const online = useOnlineStatus()
  const local = useQuery({
    queryKey: [...recallKeys.summary(sessionId), 'local'],
    queryFn: async () => (await eventStore.getSession(sessionId))?.summary ?? null,
    enabled: userId !== null,
    networkMode: 'always', // local storage: works offline
  })
  const remote = useQuery({
    queryKey: recallKeys.summary(sessionId),
    queryFn: async () => fromServer((await recallApi.closeSession(sessionId)).summary),
    enabled: userId !== null && online && synced,
    retry: false,
    staleTime: 60_000,
  })
  const data: SummaryView | null = remote.data ?? (local.data ? fromLocal(local.data) : null)
  return {
    data,
    loading: local.isPending || (remote.isPending && online && synced && !local.data),
    offline: !online || (remote.data === undefined && local.data !== null && local.data !== undefined),
  }
}
