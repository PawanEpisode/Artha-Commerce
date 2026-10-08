import { api, ApiError } from '~/lib/api'

import type {
  DocumentDetail,
  DocumentListParams,
  DocumentPage,
  DocumentPatch,
  DocumentProcessing,
  DocumentSearchResult,
  ExportJob,
  ExportOptions,
  OcrRequest,
  OcrStarted,
  PageRange,
  PagesText,
  ProgressBody,
  ProgressResult,
  RangeInput,
  ReserveBody,
  ReserveResult,
  UploadTarget,
} from './document-types'

/** Thin typed calls for the R2 document endpoints (docs/F-03-API-CONTRACT.md, "Documents"). No state, no caching. */

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
const base = (id: string) => `/notes/documents/${encodeURIComponent(id)}`

// ---- Upload lifecycle -----------------------------------------------------------------------------------------------

/** Reserve space and get the signed PUT target. A replayed `client_id` answers 200 with the same body. */
export const reserveDocument = (body: ReserveBody) =>
  api<ReserveResult>('/notes/documents/', { method: 'POST', body: json(body) })

/** "Replace edition": reserves the newer file as a document that remembers the old one (same answer as `reserveDocument`). */
export const reserveReplacement = (target: { documentId: string; editionLabel?: string }, body: ReserveBody) =>
  api<ReserveResult>(`${base(target.documentId)}/replace/`, {
    method: 'POST',
    body: json({
      client_id: body.client_id,
      filename: body.filename,
      bytes: body.bytes,
      mime: body.mime,
      ...(body.page_count_hint ? { page_count_hint: body.page_count_hint } : {}),
      ...(target.editionLabel?.trim() ? { edition_label: target.editionLabel.trim() } : {}),
    }),
  })

export const completeDocument = (id: string) =>
  api<DocumentDetail>(`${base(id)}/complete/`, { method: 'POST', body: '{}' })

export const abortDocument = (id: string) =>
  api<{ id: string; status: 'expired' }>(`${base(id)}/abort/`, { method: 'POST', body: '{}' })

/**
 * PUT the bytes to the signed URL with progress (fetch cannot report upload progress). Resolves when the object is
 * stored; rejects with `ApiError` (status 0 for a network failure) or an `AbortError` when `signal` aborts.
 * The signed URL is not an API route, so no Authorization header is sent.
 */
export function uploadDocumentBytes(
  target: UploadTarget,
  file: Blob,
  options: { signal?: AbortSignal; onProgress?: (loaded: number, total: number) => void } = {},
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open(target.method, target.url)
    for (const [name, value] of Object.entries(target.headers ?? {})) xhr.setRequestHeader(name, value)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) options.onProgress?.(e.loaded, e.total)
    }
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new ApiError(xhr.status, `Upload failed with ${xhr.status}`))
    xhr.onerror = () => reject(new ApiError(0, 'Network error during upload'))
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'))
    options.signal?.addEventListener('abort', () => xhr.abort(), { once: true })
    if (options.signal?.aborted) return xhr.abort()
    xhr.send(file)
  })
}

// ---- Read, edit, trash ----------------------------------------------------------------------------------------------

export const listDocuments = (params: DocumentListParams = {}) =>
  api<DocumentPage>(`/notes/documents/${qs({ ...params })}`)
export const getDocument = (id: string) => api<DocumentDetail>(`${base(id)}/`)
export const patchDocument = (id: string, body: DocumentPatch) =>
  api<DocumentDetail>(`${base(id)}/`, { method: 'PATCH', body: json(body) })

/** Trash (30 days, quota still counted), or purge now with `permanent` and free the quota. */
export const deleteDocument = (id: string, permanent = false) =>
  api<{ id: string; deleted_at: string; purge_after: string } | { id: string; purged: true }>(
    `${base(id)}/${qs({ permanent })}`,
    { method: 'DELETE' },
  )
export const restoreDocument = (id: string) =>
  api<DocumentDetail>(`${base(id)}/restore/`, { method: 'POST', body: '{}' })

/** Replaces the whole page-range set of the document. */
export const putRanges = (id: string, ranges: RangeInput[]) =>
  api<{ ranges: PageRange[]; relinked: number }>(`${base(id)}/chapters/`, {
    method: 'PUT',
    body: json({ ranges }),
  })

// ---- Reader ---------------------------------------------------------------------------------------------------------

/** Last write wins and idempotent, so a repeat or a reordered pair is harmless. `keepalive` lets it leave on pagehide. */
export const putProgress = (id: string, body: ProgressBody, options: { keepalive?: boolean } = {}) =>
  api<ProgressResult>(`${base(id)}/progress/`, {
    method: 'PUT',
    body: json(body),
    ...(options.keepalive ? { keepalive: true } : {}),
  })

/** The cheap poll: status, text extraction and OCR progress. */
export const getProcessing = (id: string) => api<DocumentProcessing>(`${base(id)}/processing/`)

/** At most 20 pages per call. `words` is present on OCR pages only. */
export const getPagesText = (id: string, from: number, to: number) =>
  api<PagesText>(`${base(id)}/pages/text/${qs({ from, to })}`)

export const searchDocument = (id: string, q: string, limit = 50) =>
  api<DocumentSearchResult>(`${base(id)}/search/${qs({ q, limit })}`)

// ---- OCR and exports ------------------------------------------------------------------------------------------------

export const startOcr = (id: string, body: OcrRequest) =>
  api<OcrStarted>(`${base(id)}/ocr/`, { method: 'POST', body: json(body) })

export const createDocumentExport = (id: string, body: { client_id: string; options: ExportOptions }) =>
  api<{ export: ExportJob }>(`${base(id)}/exports/`, { method: 'POST', body: json(body) })
export const createArchiveExport = (clientId: string) =>
  api<{ export: ExportJob }>('/notes/export/archive/', { method: 'POST', body: json({ client_id: clientId }) })
export const getExport = (id: string) => api<ExportJob>(`/notes/exports/${encodeURIComponent(id)}/`)

// ---- Resumable upload (R3) ------------------------------------------------------------------------------------------

export interface ResumableState {
  part_size: number
  parts: number
  done: Array<{ number: number; etag: string; size: number }>
}

/** Opens the multipart upload, or says which parts storage already holds (so a retry continues where it stopped). */
export const startResumable = (id: string) =>
  api<ResumableState>(`${base(id)}/resumable/`, { method: 'POST', body: '{}' })

/** One short-lived PUT URL per requested part (at most 20 at a time). */
export const signParts = (id: string, numbers: number[]) =>
  api<{ parts: Array<{ number: number; url: string }> }>(`${base(id)}/resumable/parts/`, {
    method: 'POST',
    body: json({ numbers }),
  })

/** Joins the parts. The server checks them against what storage holds. */
export const finishResumable = (id: string, parts: number[]) =>
  api<{ joined: number }>(`${base(id)}/resumable/complete/`, { method: 'POST', body: json({ parts }) })

/** PUT one part to its signed URL, with progress. Same failure shape as `uploadDocumentBytes`. */
export function putPart(
  url: string,
  part: Blob,
  options: { signal?: AbortSignal; onProgress?: (loaded: number) => void } = {},
): Promise<void> {
  return uploadDocumentBytes({ url, method: 'PUT', expires_at: '' }, part, {
    signal: options.signal,
    onProgress: (loaded) => options.onProgress?.(loaded),
  })
}
