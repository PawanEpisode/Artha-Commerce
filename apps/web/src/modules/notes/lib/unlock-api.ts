import { api } from '~/lib/api'

/** Unlock for search (R3): the password goes in this one request body and nowhere else. 202 means "queued". */
export const unlockDocument = (docId: string, password: string) =>
  api<{ document_id: string; unlock_status: string }>(`/notes/documents/${encodeURIComponent(docId)}/unlock/`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  })
