import { api, ApiError } from '~/lib/api'

import { type AggregateParams, aggregateQuery } from './filter-schema'
import type { MarkSearchHit, PdfSearchHit, SearchMeta } from './library-types'
import type {
  AggregateItem,
  ChangesPage,
  ChapterOverview,
  ChapterSuggestion,
  ClipSource,
  Note,
  NoteCreate,
  NotePatch,
  NoteSummary,
  Page,
  PatchResult,
  SearchHit,
  SubjectCounts,
  Tag,
  Usage,
  VersionDetail,
  VersionRow,
} from './types'

const json = (body: unknown) => JSON.stringify(body)
const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue
    query.set(key, value === true ? '1' : String(value))
  }
  const text = query.toString()
  return text ? `?${text}` : ''
}

/** A fresh idempotency key per user action. The server ignores a repeated one, so retries never duplicate a note. */
export const newClientId = () => crypto.randomUUID()

// ---- Notes ----------------------------------------------------------------------------------------------------------

export interface ListParams {
  level?: string
  subject?: string
  chapter?: string
  topic?: string
  tag?: string
  unfiled?: boolean
  pinned?: boolean
  trashed?: boolean
  q?: string
  cursor?: string
  limit?: number
}

export const listNotes = (params: ListParams = {}) => api<Page<NoteSummary>>(`/notes/${qs({ ...params })}`)
export const getNote = (id: string) => api<Note>(`/notes/${id}/`)

/** Request shapes are built apart from the call so the offline queue can store and replay exactly the same request. */
/** The client owns the note id: `PUT notes/{id}/` is an idempotent create (201 new, 200 already there, 404 not yours). */
export const createNoteRequest = (id: string, body: Omit<NoteCreate, 'client_id'>) => ({
  method: 'PUT' as const,
  path: `/notes/${id}/`,
  body: { client_id: id, ...body },
})
export const setItemTagsRequest = (noteId: string, tagIds: string[]) => ({
  method: 'PUT' as const,
  path: '/notes/items/tags/',
  body: { item_type: 'note', item_id: noteId, tag_ids: tagIds },
})
export const patchNoteRequest = (id: string, body: NotePatch) => ({
  method: 'PATCH' as const,
  path: `/notes/${id}/`,
  body: { ...body },
})
export const deleteNoteRequest = (id: string) => ({ method: 'DELETE' as const, path: `/notes/${id}/`, body: {} })
export const restoreNoteRequest = (id: string) => ({ method: 'POST' as const, path: `/notes/${id}/restore/`, body: {} })
export const clipRequest = (body: {
  client_id: string
  text_md: string
  source: ClipSource
  chapter_id?: string | null
  topic_id?: string | null
  tag_ids?: string[]
}) => ({ method: 'POST' as const, path: '/notes/clips/', body: { ...body } })

type Request = { method: 'POST' | 'PATCH' | 'DELETE' | 'PUT'; path: string; body: Record<string, unknown> }
const send = <T>(request: Request) =>
  api<T>(request.path, { method: request.method, body: request.method === 'DELETE' ? undefined : json(request.body) })

export const createNote = (id: string, body: Omit<NoteCreate, 'client_id'>) => send<Note>(createNoteRequest(id, body))
export const patchNote = (id: string, body: NotePatch) => send<PatchResult>(patchNoteRequest(id, body))
export const deleteNote = (id: string) =>
  send<{ id: string; deleted_at: string; purge_after: string }>(deleteNoteRequest(id))
export const restoreNote = (id: string) => send<Note>(restoreNoteRequest(id))
export const createClip = (body: Parameters<typeof clipRequest>[0]) =>
  send<{ note: Note; created: boolean }>(clipRequest(body))

export const listVersions = (id: string) => api<{ items: VersionRow[] }>(`/notes/${id}/versions/`).then((r) => r.items)
export const getVersion = (id: string, rev: number) => api<VersionDetail>(`/notes/${id}/versions/${rev}/`)
export const restoreVersion = (id: string, rev: number) =>
  api<Note>(`/notes/${id}/versions/${rev}/restore/`, { method: 'POST', body: '{}' })
export const listChanges = (since?: string) => api<ChangesPage>(`/notes/changes/${qs({ since, limit: 500 })}`)

// ---- Aggregate, counts, overview, search ------------------------------------------------------------------------------

export const getAggregate = (params: AggregateParams, limit = 30) =>
  api<Page<AggregateItem>>(`/notes/aggregate/?${aggregateQuery(params, limit)}`)
export const getCounts = (level: string, subject: string) =>
  api<SubjectCounts>(`/notes/aggregate/counts/${qs({ level, subject })}`)
export const getOverview = (level: string, subject: string, chapter: string) =>
  api<ChapterOverview>(`/notes/chapters/${encodeURIComponent(chapter)}/overview/${qs({ level, subject })}`)
export const searchNotes = (params: {
  q: string
  scope?: string
  level?: string
  subject?: string
  chapter?: string
  cursor?: string
  limit?: number
}) => api<Page<SearchHit | PdfSearchHit | MarkSearchHit> & { meta?: SearchMeta }>(`/notes/search/${qs({ ...params })}`)

// ---- Tags and suggestions ---------------------------------------------------------------------------------------------

export const listTags = () => api<{ items: Tag[] }>('/notes/tags/').then((r) => r.items)
export const createTag = (input: { name: string; color_key?: string | null }) =>
  api<Tag>('/notes/tags/', { method: 'POST', body: json(input) })
export const deleteTag = (id: string) => api<void>(`/notes/tags/${id}/`, { method: 'DELETE' })
export const setItemTags = (noteId: string, tagIds: string[]) =>
  send<{ tags: Tag[] }>(setItemTagsRequest(noteId, tagIds))
export const suggestChapters = (text: string, levelId?: string) =>
  api<{ suggestions: ChapterSuggestion[] }>('/notes/items/chapter-suggest/', {
    method: 'POST',
    body: json({ text, level_id: levelId }),
  }).then((r) => r.suggestions)

// ---- Usage, account ---------------------------------------------------------------------------------------------------

export const getUsage = () => api<Usage>('/notes/usage/')
export const exportAll = () => api<Record<string, unknown>>('/notes/export/')
export const deleteAll = () => api<Record<string, number>>('/notes/', { method: 'DELETE' })

// ---- Images (media module) ----------------------------------------------------------------------------------------------

export const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'] as const

/** Reserve, upload and complete one note image. Resolves with the attachment id to put in the Markdown. */
export async function uploadNoteImage(file: File): Promise<string> {
  const reservation = await api<{
    attachment: { id: string }
    upload: { url: string; method: string; headers?: Record<string, string> }
  }>('/media/uploads/', {
    method: 'POST',
    body: json({ kind: 'note_image', filename: file.name, mime: file.type, bytes: file.size }),
  })
  const put = await fetch(reservation.upload.url, {
    method: reservation.upload.method,
    headers: reservation.upload.headers,
    body: file,
  })
  if (!put.ok) throw new ApiError(put.status || 0, `Upload failed with ${put.status}`)
  await api(`/media/uploads/${reservation.attachment.id}/complete/`, { method: 'POST', body: '{}' })
  return reservation.attachment.id
}

export const getAttachmentUrl = (id: string) =>
  api<{ url: string; expires_at: string }>(`/media/attachments/${id}/url/`)
