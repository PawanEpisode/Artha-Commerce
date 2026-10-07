import { api, ApiError } from '~/lib/api'

import type {
  AnnotationConflictDetail,
  BatchOpBody,
  BatchResponse,
  CardKind,
  DeltaPage,
  NotesSettings,
  WriteResponse,
} from './annotation-types'
import { errorCode } from './errors'

const json = (body: unknown) => JSON.stringify(body)

/** Page size of the delta feed (the API's maximum). A page may hold a few more rows: it never ends inside one `seq`. */
export const DELTA_LIMIT = 500
/** Most operations the API takes in one batch. */
export const MAX_BATCH = 100

export const getSettings = () => api<NotesSettings>('/notes/settings/')

/** Marks changed after `sinceSeq`, tombstones included, in `seq` order. */
export const getDelta = (documentId: string, sinceSeq: number, limit = DELTA_LIMIT) =>
  api<DeltaPage>(`/notes/documents/${documentId}/annotations/?since_seq=${sinceSeq}&limit=${limit}`)

/**
 * Request shapes are built apart from the calls so the offline queue stores and replays exactly the same request.
 * The batch op carries `op` and `id` on top of the PUT body; the single request drops them.
 */
export interface MarkRequest {
  method: 'PUT' | 'DELETE' | 'POST'
  path: string
  body: Record<string, unknown>
}

export function requestOf(op: BatchOpBody): MarkRequest {
  const { op: kind, id, ...rest } = op
  if (kind === 'delete')
    return { method: 'DELETE', path: `/notes/annotations/${id}/`, body: { base_rev: rest.base_rev } }
  if (kind === 'restore') return { method: 'POST', path: `/notes/annotations/${id}/restore/`, body: {} }
  return { method: 'PUT', path: `/notes/annotations/${id}/`, body: rest }
}

export const sendMark = (op: BatchOpBody) => {
  const request = requestOf(op)
  return api<WriteResponse>(request.path, {
    method: request.method,
    // The API reads a DELETE body (`base_rev`), unlike the notes' DELETE.
    body: json(request.body),
  })
}

export const putMark = (op: BatchOpBody) => sendMark({ ...op, op: 'upsert' })
export const deleteMark = (id: string, baseRev?: number) =>
  sendMark({ op: 'delete', id, ...(baseRev === undefined ? {} : { base_rev: baseRev }) })
export const restoreMark = (id: string) => sendMark({ op: 'restore', id })

export const batchMarks = (documentId: string, ops: BatchOpBody[]) =>
  api<BatchResponse>('/notes/annotations/batch/', { method: 'POST', body: json({ document_id: documentId, ops }) })

export const makeCard = (annotationId: string, clientId: string, kind?: CardKind) =>
  api<{ card_id: string; existing: boolean }>(`/notes/annotations/${annotationId}/card/`, {
    method: 'POST',
    body: json({ client_id: clientId, ...(kind ? { kind } : {}) }),
  })

/** 409 `annotation_conflict`: both versions of a comment that could not be merged. */
export function annotationConflict(error: unknown): AnnotationConflictDetail | null {
  if (!(error instanceof ApiError) || error.status !== 409 || errorCode(error) !== 'annotation_conflict') return null
  const details = (error.body as { error?: { details?: unknown } } | undefined)?.error?.details
  return details ? (details as AnnotationConflictDetail) : null
}

/** 503 `recall_unavailable`: no recall provider is registered (the card button should not have been shown). */
export const isRecallUnavailable = (error: unknown) =>
  error instanceof ApiError && error.status === 503 && errorCode(error) === 'recall_unavailable'
/** 422 `no_text`: nothing to make a card from. */
export const isNoText = (error: unknown) =>
  error instanceof ApiError && error.status === 422 && errorCode(error) === 'no_text'
