import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'

import { trackRecall } from '../lib/analytics'
import { recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'
import { useRefresh } from './useCardScreens'

/** The updates she has received on a deck. Loads when the list is opened, not with the deck page. */
export const useUpdateHistory = (subscriptionId: string, enabled: boolean) =>
  useQuery({
    queryKey: recallKeys.updateHistory(subscriptionId),
    queryFn: async () => {
      const rows = await recallApi.updateHistory(subscriptionId)
      trackRecall('recall_update_history_viewed', { updates: rows.length })
      return rows
    },
    enabled: enabled && subscriptionId !== '',
    retry: false,
  })

/** What changed in one card. Loads when its section is opened. */
export const useCardChanges = (cardId: string, enabled: boolean) =>
  useQuery({
    queryKey: recallKeys.cardChanges(cardId),
    queryFn: async () => {
      const c = await recallApi.cardChanges(cardId)
      trackRecall('recall_card_changes_viewed', { versions: c.versions.length, waiting: c.waiting })
      return c
    },
    enabled,
    retry: false,
  })

/** Say a card is in her own words, or take it back. The card and the card lists are refetched. */
export function useAttest(cardId: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (ownWords: boolean) => recallApi.attest(cardId, ownWords),
    onSuccess: (r) => {
      trackRecall('recall_own_words_set', { attested: r.attested })
      refresh(cardId)
    },
  })
}

/**
 * A card from a question she got wrong. One id per tap of the button for as long as the screen lives, so a retry after a dropped
 * connection returns the card the first try made instead of a second one.
 */
export function useCardFromQuestion(questionId: string, versionId: string) {
  const refresh = useRefresh()
  const qc = useQueryClient()
  const clientId = useRef<string>(crypto.randomUUID())
  return useMutation({
    mutationFn: () =>
      recallApi.cardFromQuestion({ question_id: questionId, version_id: versionId, client_id: clientId.current }),
    onSuccess: (r) => {
      trackRecall('recall_question_card_made', { existing: r.existing })
      refresh()
      void qc.invalidateQueries({ queryKey: recallKeys.today })
    },
  })
}
