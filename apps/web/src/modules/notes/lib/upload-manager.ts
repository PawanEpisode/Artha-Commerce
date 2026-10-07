/**
 * The upload state machine (FR-F03-02, PRD 7.3 "Upload sheet and failure states"). Framework free and module level, so an
 * upload goes on while the student moves between screens: reserve, send the bytes (progress, cancel), complete, then poll
 * `processing/` until the server has scanned and inspected the file. React reads it through `useUploads`.
 *
 *   reserving -> uploading -> completing -> processing -> ready | duplicate
 *   any step  -> failed (reason: network, server, too_large, too_many_pages, type, scan_rejected, quota)
 *
 * The reservation is kept 30 minutes by the server, so a Retry within that time replays the same `client_id` (the API answers
 * with a fresh signed URL); after it, a new `client_id` makes a new reservation. R2 restarts the file on retry (R3 resumes).
 * Nothing here stores the file name anywhere but memory; analytics get ranges only.
 */
import type { DocumentDetail, DocumentProcessing, ReserveBody, ReserveResult, UploadTarget } from './document-types'
import {
  type DocumentQuotaDetails,
  documentQuotaExceeded,
  fileTooLarge,
  isUnsupportedType,
  requestIdOf,
  tooManyPages,
} from './errors'

export const RESERVATION_MS = 30 * 60_000
export const PROCESSING_POLL_MS = 2500
/** After this long without an answer the manager stops polling; the library card keeps watching on its own. */
export const PROCESSING_GIVE_UP_MS = 10 * 60_000

export type UploadPhase = 'reserving' | 'uploading' | 'completing' | 'processing' | 'ready' | 'duplicate' | 'failed'

export type UploadFailureReason =
  'network' | 'server' | 'too_large' | 'too_many_pages' | 'type' | 'scan_rejected' | 'quota'

export interface UploadFailure {
  reason: UploadFailureReason
  /** Plain words for the student. Never a stack, a URL or a file name. */
  message: string
  retryable: boolean
  requestId?: string
  quota?: DocumentQuotaDetails
  limit?: number
  /** For `scan_rejected`: the server's `status_reason`. */
  statusReason?: string | null
}

export interface UploadItem {
  /** The `client_id` of the reservation, also this item's key. */
  id: string
  fileName: string
  bytes: number
  pages: number | null
  phase: UploadPhase
  loaded: number
  documentId?: string
  failure?: UploadFailure
  /** Set once the file is inspected. */
  scanned?: boolean
  encrypted?: boolean
  duplicateOf?: string | null
  startedAt: number
  reservedAt?: number
}

export interface UploadOptions {
  pages: number | null
  sourceKind?: ReserveBody['source_kind']
  chapterId?: string | null
  topicId?: string | null
}

export interface UploadDeps {
  reserve: (body: ReserveBody) => Promise<ReserveResult>
  send: (
    target: UploadTarget,
    file: Blob,
    options: { signal: AbortSignal; onProgress: (loaded: number, total: number) => void },
  ) => Promise<void>
  complete: (id: string) => Promise<DocumentDetail>
  abort: (id: string) => Promise<unknown>
  processing: (id: string) => Promise<DocumentProcessing>
  document: (id: string) => Promise<DocumentDetail>
  purge: (id: string) => Promise<unknown>
  now: () => number
  newId: () => string
  /** `setTimeout`, replaceable so tests need no real clock. */
  wait: (ms: number) => Promise<void>
}

export type UploadEvent =
  | { type: 'started'; item: UploadItem }
  | { type: 'completed'; item: UploadItem; document: DocumentDetail; durationMs: number }
  | { type: 'failed'; item: UploadItem; failure: UploadFailure }

const message = {
  network: 'Upload paused, connection lost.',
  server: 'Something went wrong on our side.',
  notUploaded: 'The upload did not finish.',
  tooManyUploads: 'Too many uploads in a short time. Wait a few minutes and try again.',
  type: 'This does not look like a PDF.',
  scan: 'We could not accept this file.',
}

/** Plain-words reason for a refused file (`status_reason`); never more detail than a code. */
export function rejectionMessage(reason: string | null | undefined): string {
  switch (reason) {
    case 'malware':
      return 'We could not accept this file because our check found something harmful in it. It was removed.'
    case 'pdf_corrupt':
    case 'decode_failed':
      return 'We could not accept this file because it is damaged and cannot be opened. It was removed.'
    case 'type_mismatch':
      return 'We could not accept this file because it is not really a PDF. It was removed.'
    case 'too_many_pages':
      return 'We could not accept this file because it has more pages than your plan allows. It was removed.'
    case 'too_large':
      return 'We could not accept this file because it is larger than your plan allows. It was removed.'
    default:
      return 'We could not accept this file. It was removed.'
  }
}

/** Turns whatever a step threw into the failure the UI words. Pure, so every case is unit tested. */
export function classifyUploadError(error: unknown, step: 'reserve' | 'send' | 'complete' | 'other'): UploadFailure {
  const requestId = requestIdOf(error)
  const quota = documentQuotaExceeded(error)
  if (quota && (quota.kind === 'storage' || quota.kind === 'documents'))
    return { reason: 'quota', message: 'There is no room left for this file.', retryable: false, quota }
  const tooLarge = fileTooLarge(error)
  if (tooLarge)
    return {
      reason: 'too_large',
      message: `That file is over the ${tooLarge.limitMb || 50} MB limit.`,
      retryable: false,
      limit: tooLarge.limitMb,
    }
  const pages = tooManyPages(error)
  if (pages)
    return {
      reason: 'too_many_pages',
      message: `That PDF has more than ${pages.limit || 1000} pages.`,
      retryable: false,
      limit: pages.limit,
    }
  if (isUnsupportedType(error)) return { reason: 'type', message: message.type, retryable: false }
  const status = (error as { status?: unknown } | null)?.status
  if (status === 0 || (error instanceof TypeError && step !== 'other'))
    return { reason: 'network', message: message.network, retryable: true }
  if (status === 429) return { reason: 'server', message: message.tooManyUploads, retryable: true, requestId }
  if (status === 409 && step === 'complete')
    return { reason: 'network', message: message.notUploaded, retryable: true, requestId }
  // A signed URL the storage refused (expired or a bad signature) is retried from the reservation.
  if (step === 'send' && (status === 403 || status === 401))
    return { reason: 'network', message: message.network, retryable: true }
  return { reason: 'server', message: message.server, retryable: true, requestId }
}

const isAbortError = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

type Listener = () => void

export function createUploadManager(deps: UploadDeps) {
  let items: UploadItem[] = []
  const files = new Map<string, File>()
  const options = new Map<string, UploadOptions>()
  const controllers = new Map<string, AbortController>()
  const listeners = new Set<Listener>()
  const events = new Set<(event: UploadEvent) => void>()

  const emit = () => listeners.forEach((l) => l())
  const patch = (id: string, change: Partial<UploadItem>) => {
    let changed = false
    items = items.map((item) => {
      if (item.id !== id) return item
      changed = true
      return { ...item, ...change }
    })
    if (changed) emit()
  }
  const find = (id: string) => items.find((i) => i.id === id)
  const fire = (event: UploadEvent) => events.forEach((l) => l(event))

  async function fail(id: string, failure: UploadFailure) {
    const item = find(id)
    if (!item) return
    patch(id, { phase: 'failed', failure })
    const current = find(id)
    if (current) fire({ type: 'failed', item: current, failure })
  }

  async function pollUntilInspected(documentId: string, signal: AbortSignal): Promise<DocumentProcessing | null> {
    const started = deps.now()
    for (;;) {
      if (signal.aborted) return null
      let state: DocumentProcessing
      try {
        state = await deps.processing(documentId)
      } catch (error) {
        const status = (error as { status?: unknown } | null)?.status
        // A lost connection while polling is not a failed upload: wait and ask again.
        if (status === 404) throw error
        state = { status: 'scanning' } as DocumentProcessing
      }
      if (state.status === 'ready' || state.status === 'needs_password') return state
      if (state.status === 'rejected' || state.status === 'failed' || state.status === 'expired') return state
      if (deps.now() - started > PROCESSING_GIVE_UP_MS) return null
      await deps.wait(PROCESSING_POLL_MS)
    }
  }

  async function run(id: string) {
    const file = files.get(id)
    const item = find(id)
    if (!file || !item) return
    const controller = new AbortController()
    controllers.set(id, controller)
    const opts = options.get(id)
    let step: 'reserve' | 'send' | 'complete' | 'other' = 'reserve'
    try {
      patch(id, { phase: 'reserving', loaded: 0, failure: undefined })
      const reservation = await deps.reserve({
        client_id: id,
        filename: file.name,
        bytes: file.size,
        mime: 'application/pdf',
        ...(item.pages ? { page_count_hint: item.pages } : {}),
        ...(opts?.sourceKind ? { source_kind: opts.sourceKind } : {}),
        ...(opts?.chapterId ? { chapter_id: opts.chapterId, topic_id: opts.topicId ?? null } : {}),
      })
      const documentId = reservation.document.id
      patch(id, { documentId, reservedAt: item.reservedAt ?? deps.now() })
      if (controller.signal.aborted) {
        void deps.abort(documentId).catch(() => undefined)
        return
      }

      // A replay of a file that already got past the upload (status beyond `reserved`) has no new URL: skip to completing.
      if (reservation.upload) {
        step = 'send'
        patch(id, { phase: 'uploading', loaded: 0 })
        await deps.send(reservation.upload, file, {
          signal: controller.signal,
          onProgress: (loaded) => patch(id, { loaded }),
        })
      }
      step = 'complete'
      patch(id, { phase: 'completing', loaded: file.size })
      await deps.complete(documentId)

      step = 'other'
      patch(id, { phase: 'processing' })
      const state = await pollUntilInspected(documentId, controller.signal)
      if (controller.signal.aborted) return
      if (!state)
        return fail(id, {
          reason: 'server',
          message: 'Still checking this file. It will appear in your library soon.',
          retryable: false,
        })
      if (state.status === 'rejected')
        return fail(id, {
          reason: 'scan_rejected',
          message: rejectionMessage(state.status_reason),
          retryable: false,
          statusReason: state.status_reason,
        })
      if (state.status === 'failed' || state.status === 'expired')
        return fail(id, { reason: 'server', message: message.server, retryable: true })

      const document = await deps.document(documentId)
      const encrypted = document.is_encrypted || state.status === 'needs_password'
      const duplicateOf = document.duplicate_of
      patch(id, {
        phase: duplicateOf ? 'duplicate' : 'ready',
        scanned: document.is_scanned === true,
        encrypted,
        duplicateOf,
        pages: document.page_count ?? find(id)?.pages ?? null,
      })
      const done = find(id)
      if (done) fire({ type: 'completed', item: done, document, durationMs: deps.now() - done.startedAt })
    } catch (error) {
      if (controller.signal.aborted || isAbortError(error)) return
      await fail(id, classifyUploadError(error, step))
    } finally {
      controllers.delete(id)
    }
  }

  /** Starts one upload. The caller has already run `checkBeforeUpload` (nothing moves for a refused file). */
  function start(file: File, opts: UploadOptions): string {
    const id = deps.newId()
    files.set(id, file)
    options.set(id, opts)
    items = [
      ...items,
      {
        id,
        fileName: file.name,
        bytes: file.size,
        pages: opts.pages,
        phase: 'reserving',
        loaded: 0,
        startedAt: deps.now(),
      },
    ]
    emit()
    const started = find(id)
    if (started) fire({ type: 'started', item: started })
    void run(id)
    return id
  }

  /** Removes the item from the list (a finished or failed one, or after cancelling). */
  function dismiss(id: string) {
    files.delete(id)
    options.delete(id)
    items = items.filter((i) => i.id !== id)
    emit()
  }

  return {
    subscribe(listener: Listener) {
      listeners.add(listener)
      return () => void listeners.delete(listener)
    },
    getSnapshot: () => items,
    onEvent(listener: (event: UploadEvent) => void) {
      events.add(listener)
      return () => void events.delete(listener)
    },
    start,
    dismiss,

    /** Restarts the file. Within 30 minutes of the reservation the same `client_id` is replayed; later a new one is used. */
    retry(id: string) {
      const item = find(id)
      if (!item || item.phase !== 'failed' || !item.failure?.retryable || !files.has(id)) return
      const expired = item.reservedAt !== undefined && deps.now() - item.reservedAt > RESERVATION_MS
      if (!expired) return void run(id)
      const file = files.get(id) as File
      const opts = options.get(id) ?? { pages: item.pages }
      dismiss(id)
      start(file, opts)
    },

    /** Stops the transfer and releases the reservation (best effort: the server also expires it after 30 minutes). */
    cancel(id: string) {
      const item = find(id)
      controllers.get(id)?.abort()
      if (item?.documentId && item.phase !== 'ready' && item.phase !== 'duplicate' && item.phase !== 'processing')
        void deps.abort(item.documentId).catch(() => undefined)
      dismiss(id)
    },

    /** "Keep both": the new copy stays; the prompt goes away. */
    keepBoth(id: string) {
      patch(id, { phase: 'ready', duplicateOf: null })
    },

    /** "Open it": the new copy is byte-for-byte the same and has no marks, so it is removed for good and its space freed. */
    async discardDuplicate(id: string) {
      const item = find(id)
      if (item?.documentId) await deps.purge(item.documentId).catch(() => undefined)
      dismiss(id)
    },
  }
}

export type UploadManager = ReturnType<typeof createUploadManager>

/** Items still moving (the chip counts these). */
export const activeUploads = (items: readonly UploadItem[]) =>
  items.filter(
    (i) => i.phase === 'reserving' || i.phase === 'uploading' || i.phase === 'completing' || i.phase === 'processing',
  )

/** 0..100 for a transfer; the other phases do not have a percentage. */
export const uploadPercent = (item: Pick<UploadItem, 'loaded' | 'bytes' | 'phase'>): number | null =>
  item.phase === 'uploading' || item.phase === 'completing'
    ? item.bytes > 0
      ? Math.min(100, Math.round((item.loaded / item.bytes) * 100))
      : 0
    : null
