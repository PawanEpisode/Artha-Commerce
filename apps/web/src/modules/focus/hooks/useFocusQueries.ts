import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { isFeatureDisabled, listSessions } from '../lib/api'
import { focusKeys } from '../lib/keys'

const noRetryWhenOff = (count: number, error: unknown) => !isFeatureDisabled(error) && count < 1

/** Rounds finished on one day (for the "N rounds today" line). */
export function useRoundsOn(date: string) {
  return useQuery({
    queryKey: [...focusKeys.sessions, 'day', date],
    queryFn: () => listSessions({ from: date, to: date, limit: 100 }),
    select: (page) => page.results.length,
    retry: noRetryWhenOff,
  })
}

export function useHistory(params: { from?: string; to?: string }) {
  return useInfiniteQuery({
    queryKey: [...focusKeys.sessions, 'history', params],
    queryFn: ({ pageParam }) => listSessions({ ...params, cursor: pageParam, limit: 50 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: noRetryWhenOff,
  })
}
