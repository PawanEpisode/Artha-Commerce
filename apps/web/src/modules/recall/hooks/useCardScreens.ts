import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  type BulkAction,
  type BulkArgs,
  type CardStateAction,
  type CreateCardBody,
  type PatchCardBody,
  recallApi,
} from '../lib/api'
import { cardFailure } from '../lib/cardErrors'
import { cardQueue } from '../lib/cardQueue'
import { recallKeys } from '../lib/keys'
import { useOnlineStatus, useRecallUser } from './useRecallBasics'

export const useCard = (id: string) =>
  useQuery({ queryKey: recallKeys.card(id), queryFn: () => recallApi.card(id), retry: false })

export const useCardHistory = (id: string) =>
  useQuery({ queryKey: recallKeys.cardHistory(id), queryFn: () => recallApi.cardHistory(id), retry: false })

/** Anything about the cards changed: the lists, the open card and what today's plan counts. */
function useRefresh() {
  const qc = useQueryClient()
  return useCallback(
    (id?: string) => {
      void qc.invalidateQueries({ queryKey: ['recall', 'cards'] })
      void qc.invalidateQueries({ queryKey: recallKeys.today })
      void qc.invalidateQueries({ queryKey: recallKeys.pack })
      if (id) void qc.invalidateQueries({ queryKey: recallKeys.card(id) })
    },
    [qc],
  )
}

export function useCreateCard() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: CreateCardBody) => recallApi.createCard(body), onSuccess: () => refresh() })
}

export function usePatchCard(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: PatchCardBody) => recallApi.patchCard(id, body),
    onSuccess: () => refresh(id),
  })
}

export function useDeleteCard() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (id: string) => recallApi.deleteCard(id), onSuccess: (_r, id) => refresh(id) })
}

export function useUndoDelete() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (token: string) => recallApi.undoDelete(token),
    onSuccess: (card) => refresh(card.id),
  })
}

export function useCardState(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (action: CardStateAction) => recallApi.setCardState(id, action),
    onSuccess: () => refresh(id),
  })
}

export function useBulkCards() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (v: { ids: string[]; action: BulkAction; args?: BulkArgs }) =>
      recallApi.bulkCards(v.ids, v.action, v.args),
    onSuccess: () => refresh(),
  })
}

/**
 * Cards written offline. `save` tries the server first when online, and queues the card (with its own id, so a retry
 * never doubles it) when the network fails or the student is offline. The queue is sent on mount and when back online.
 */
export function useCardQueue() {
  const userId = useRecallUser()
  const online = useOnlineStatus()
  const refresh = useRefresh()
  const [pending, setPending] = useState(() => (userId ? cardQueue.count(userId) : 0))
  const running = useRef(false)

  const flush = useCallback(async () => {
    if (!userId || running.current) return
    running.current = true
    try {
      for (const item of cardQueue.list(userId)) {
        try {
          await recallApi.createCard(item.body)
          cardQueue.remove(userId, item.body.client_id)
        } catch (error) {
          const failure = cardFailure(error)
          if (failure.kind === 'network' || failure.kind === 'throttled') break
          // The server will not take this one (duplicate, invalid, over the limit): keep nothing that can never succeed.
          cardQueue.remove(userId, item.body.client_id)
        }
      }
    } finally {
      running.current = false
      setPending(cardQueue.count(userId))
      refresh()
    }
  }, [userId, refresh])

  useEffect(() => {
    if (online && pending > 0) void flush()
  }, [online, pending, flush])

  const queue = useCallback(
    (body: CreateCardBody) => {
      if (!userId) return 'unsaved' as const
      const outcome = cardQueue.add(userId, body)
      setPending(cardQueue.count(userId))
      return outcome
    },
    [userId],
  )

  return { pending, queue, flush }
}
