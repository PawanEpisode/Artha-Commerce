import { api } from '~/lib/api'

import type { Attention, AttentionAction, AttentionItem } from './replace-types'

const base = (id: string) => `/notes/documents/${encodeURIComponent(id)}/attention/`

/** Replace edition (R3): the marks of the old edition that wait for the student's decision. */
export const getAttention = (docId: string) => api<Attention>(base(docId))

export const resolveAttention = (docId: string, itemId: string, action: AttentionAction, page?: number) =>
  api<AttentionItem>(`${base(docId)}${encodeURIComponent(itemId)}/`, {
    method: 'POST',
    body: JSON.stringify({ action, ...(page ? { page } : {}) }),
  })
