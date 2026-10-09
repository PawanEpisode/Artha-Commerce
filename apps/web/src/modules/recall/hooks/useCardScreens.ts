import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  type BulkAction,
  type BulkArgs,
  type CardStateAction,
  type CreateCardBody,
  type PatchCardBody,
  recallApi,
} from '../lib/api'
import { cardEditQueue } from '../lib/cardEditQueue'
import { flushEdits } from '../lib/cardEditSync'
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
 * Cards and edits written offline. `queue` keeps a new card (with its own id, so a retry never doubles it) and
 * `queueEdit` keeps an edit of an existing one. Both are sent on mount and when the connection is back; `attention` lists
 * the edits the server could not take on its own.
 */
export function useCardQueue() {
  const userId = useRecallUser()
  const online = useOnlineStatus()
  const refresh = useRefresh()
  const [tick, setTick] = useState(0)
  const running = useRef(false)
  const snapshot = useMemo(
    () => ({
      pending: userId ? cardQueue.count(userId) : 0,
      editsWaiting: userId ? cardEditQueue.waiting(userId) : 0,
      attention: userId ? cardEditQueue.needsAttention(userId) : [],
    }),
    // `tick` is the signal that local storage changed
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [userId, tick],
  )

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
          if (failure.kind === 'network' || failure.kind === 'throttled') return
          // The server will not take this one (duplicate, invalid, over the limit): keep nothing that can never succeed.
          cardQueue.remove(userId, item.body.client_id)
        }
      }
      await flushEdits(userId)
    } finally {
      running.current = false
      setTick((t) => t + 1)
      refresh()
    }
  }, [userId, refresh])

  const waiting = snapshot.pending + snapshot.editsWaiting
  useEffect(() => {
    if (online && waiting > 0) void flush()
  }, [online, waiting, flush])

  const queue = useCallback(
    (body: CreateCardBody) => {
      if (!userId) return 'unsaved' as const
      const outcome = cardQueue.add(userId, body)
      setTick((t) => t + 1)
      return outcome
    },
    [userId],
  )

  const queueEdit = useCallback(
    (edit: Parameters<typeof cardEditQueue.put>[1]) => {
      if (!userId) return 'unsaved' as const
      const outcome = cardEditQueue.put(userId, edit)
      setTick((t) => t + 1)
      return outcome
    },
    [userId],
  )

  /** Drops an edit the student chose to give up on, or one she has just settled on the card page. */
  const dropEdit = useCallback(
    (cardId: string) => {
      if (userId) cardEditQueue.remove(userId, cardId)
      setTick((t) => t + 1)
    },
    [userId],
  )

  return {
    pending: snapshot.pending,
    editsWaiting: snapshot.editsWaiting,
    attention: snapshot.attention,
    queue,
    queueEdit,
    dropEdit,
    flush,
  }
}
