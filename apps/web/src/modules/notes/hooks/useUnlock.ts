import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getDocument } from '../lib/documents-api'
import { notesKeys } from '../lib/keys'
import { unlockDocument } from '../lib/unlock-api'

const POLL_MS = 3000

/** Sends the password. It is not kept in the query cache, a store or analytics: only the request carries it. */
export function useUnlock(docId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (password: string) => unlockDocument(docId, password),
    onSuccess: () => void qc.invalidateQueries({ queryKey: notesKeys.document(docId) }),
  })
}

/** While a try is on its way the document is read again every 3 seconds, then it stops. */
export function useUnlockWatch(docId: string, active: boolean) {
  const qc = useQueryClient()
  return useQuery({
    queryKey: notesKeys.document(docId),
    queryFn: async () => {
      const doc = await getDocument(docId)
      if (doc.unlock_status === 'done') void qc.invalidateQueries({ queryKey: notesKeys.documentLists })
      return doc
    },
    enabled: active,
    refetchInterval: active ? POLL_MS : false,
  })
}
