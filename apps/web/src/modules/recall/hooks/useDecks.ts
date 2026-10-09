import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { recallApi, type ReportReason, type Tier } from '../lib/api'
import { recallKeys } from '../lib/keys'

export const useDeckLibrary = (tier?: Tier) =>
  useInfiniteQuery({
    queryKey: recallKeys.deckLibrary({ tier }),
    queryFn: ({ pageParam }) => recallApi.deckLibrary({ tier, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })

export const useMyDecks = () => useQuery({ queryKey: recallKeys.myDecks, queryFn: recallApi.myDecks })

export const useDeck = (deckId: string) =>
  useQuery({ queryKey: recallKeys.deck(deckId), queryFn: () => recallApi.deck(deckId) })

/** A subscription change reaches the cards, today's plan and the stats, so everything under `recall` is refetched. */
function useRefresh() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: recallKeys.all })
}

export function useSubscribe(deckId: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (minImportance?: Tier) =>
      recallApi.subscribe(deckId, minImportance ? { min_importance: minImportance } : {}),
    onSuccess: () => void refresh(),
  })
}

export function useUnsubscribe() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (subscriptionId: string) => recallApi.unsubscribe(subscriptionId),
    onSuccess: () => void refresh(),
  })
}

export function useResubscribe() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (subscriptionId: string) => recallApi.resubscribe(subscriptionId),
    onSuccess: () => void refresh(),
  })
}

export function useReportItem() {
  return useMutation({
    mutationFn: (v: { itemId: string; reason: ReportReason; note: string }) =>
      recallApi.reportItem(v.itemId, { reason: v.reason, note: v.note.trim() || undefined }),
  })
}
