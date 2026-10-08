import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { isFeatureDisabled, isNotFound } from '../lib/errors'
import { notesKeys } from '../lib/keys'
import { getAttention, resolveAttention } from '../lib/replace-api'
import type { AttentionAction } from '../lib/replace-types'

const POLL_MS = 3000

/** The marks of an old edition waiting for a decision. While the server is still moving them it is read every 3 seconds. */
export const useAttention = (docId: string, enabled: boolean) =>
  useQuery({
    queryKey: notesKeys.attention(docId),
    queryFn: () => getAttention(docId),
    enabled,
    retry: (failures, error) => failures < 2 && !isNotFound(error) && !isFeatureDisabled(error),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'waiting' || status === 'running' ? POLL_MS : false
    },
  })

/** Keep, save as a note or dismiss one mark. Repeating the same decision is harmless on the server. */
export function useResolveAttention(docId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, action }: { itemId: string; action: AttentionAction }) =>
      resolveAttention(docId, itemId, action),
    onSuccess: (_item, { action }) => {
      void qc.invalidateQueries({ queryKey: notesKeys.attention(docId) })
      void qc.invalidateQueries({ queryKey: notesKeys.document(docId) })
      if (action === 'note') void qc.invalidateQueries({ queryKey: notesKeys.all })
    },
  })
}
