import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import type { DocumentProcessing } from './document-types'
import { makeDocument, makeProcessing } from './testing-documents'
import {
  activeUploads,
  classifyUploadError,
  createUploadManager,
  rejectionMessage,
  RESERVATION_MS,
  type UploadDeps,
  type UploadEvent,
  uploadPercent,
} from './upload-manager'

const err = (status: number, code: string, details?: unknown, extra: object = {}) =>
  new ApiError(status, 'x', { error: { code, message: 'm', details, ...extra } })

const file = (name = 'tax.pdf', size = 1000) => new File([new Uint8Array(size)], name, { type: 'application/pdf' })
const flush = async () => {
  for (let i = 0; i < 20; i++) await Promise.resolve()
}

function setup(overrides: Partial<UploadDeps> = {}) {
  let clock = 1_000
  let n = 0
  const deps: UploadDeps = {
    reserve: vi.fn(async () => ({
      document: makeDocument({ status: 'reserved' }),
      upload: { url: 'https://s/put', method: 'PUT' as const, headers: {} },
    })),
    send: vi.fn(async (_t, f, o) => o.onProgress(f.size, f.size)),
    complete: vi.fn(async () => makeDocument({ status: 'scanning' })),
    abort: vi.fn(async () => undefined),
    processing: vi.fn(async () => makeProcessing()),
    document: vi.fn(async () => makeDocument()),
    purge: vi.fn(async () => undefined),
    now: () => clock,
    newId: () => `id-${++n}`,
    wait: vi.fn(async (ms: number) => void (clock += ms)),
    ...overrides,
  } as UploadDeps
  const manager = createUploadManager(deps)
  const events: UploadEvent[] = []
  manager.onEvent((e) => events.push(e))
  const item = (id: string) => manager.getSnapshot().find((i) => i.id === id)
  const advance = (ms: number) => void (clock += ms)
  return { deps, manager, events, item, advance }
}

describe('upload manager: the happy path', () => {
  it('goes reserving, uploading, completing, processing, ready and fires started and completed', async () => {
    const phases: string[] = []
    const { manager, events, item } = setup()
    manager.subscribe(() => {
      const p = manager.getSnapshot()[0]?.phase
      if (p && phases.at(-1) !== p) phases.push(p)
    })
    const id = manager.start(file(), { pages: 3 })
    await flush()
    expect(phases).toEqual(['reserving', 'uploading', 'completing', 'processing', 'ready'])
    expect(item(id)).toMatchObject({ phase: 'ready', scanned: false, encrypted: false, pages: 3 })
    expect(events.map((e) => e.type)).toEqual(['started', 'completed'])
    expect(activeUploads(manager.getSnapshot())).toHaveLength(0)
  })

  it('sends the page hint, source kind and chapter in the reservation', async () => {
    const { manager, deps } = setup()
    manager.start(file(), { pages: 12, sourceKind: 'coaching', chapterId: 'c1', topicId: null })
    await flush()
    expect(deps.reserve).toHaveBeenCalledWith(
      expect.objectContaining({
        client_id: 'id-1',
        bytes: 1000,
        page_count_hint: 12,
        source_kind: 'coaching',
        chapter_id: 'c1',
      }),
    )
  })

  it('reports scanned and locked files so the sheet can offer OCR or the password step', async () => {
    const { manager, item } = setup({
      processing: vi.fn(async () => makeProcessing({ status: 'needs_password' })),
      document: vi.fn(async () => makeDocument({ is_scanned: true, is_encrypted: true })),
    })
    const id = manager.start(file(), { pages: null })
    await flush()
    expect(item(id)).toMatchObject({ phase: 'ready', scanned: true, encrypted: true })
  })

  it('polls while the file is scanning, then reads the document', async () => {
    const states: DocumentProcessing[] = [
      makeProcessing({ status: 'scanning' }),
      makeProcessing({ status: 'scanning' }),
      makeProcessing(),
    ]
    const { manager, deps, item } = setup({ processing: vi.fn(async () => states.shift() as DocumentProcessing) })
    const id = manager.start(file(), { pages: null })
    await flush()
    expect(deps.processing).toHaveBeenCalledTimes(3)
    expect(deps.wait).toHaveBeenCalledTimes(2)
    expect(item(id)?.phase).toBe('ready')
  })

  it('skips the transfer when a replay says the bytes already arrived', async () => {
    const { manager, deps, item } = setup({
      reserve: vi.fn(async () => ({ document: makeDocument(), upload: null })),
    })
    const id = manager.start(file(), { pages: null })
    await flush()
    expect(deps.send).not.toHaveBeenCalled()
    expect(item(id)?.phase).toBe('ready')
  })

  it('reports progress as it moves', async () => {
    let release: () => void = () => undefined
    const { manager, item } = setup({
      send: vi.fn(async (_t, f, o) => {
        o.onProgress(f.size / 2, f.size)
        await new Promise<void>((r) => (release = r))
      }),
    })
    const id = manager.start(file('a.pdf', 1000), { pages: null })
    await flush()
    const current = item(id)
    expect(current?.phase).toBe('uploading')
    expect(current && uploadPercent(current)).toBe(50)
    release()
    await flush()
    expect(item(id)?.phase).toBe('ready')
  })
})

describe('upload manager: every failure', () => {
  const cases: Array<[string, Partial<UploadDeps>, { reason: string; retryable: boolean }]> = [
    [
      'network lost while reserving',
      { reserve: vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))) },
      { reason: 'network', retryable: true },
    ],
    [
      'server error while reserving',
      { reserve: vi.fn(async () => Promise.reject(err(500, 'internal', undefined, { request_id: 'req-9' }))) },
      { reason: 'server', retryable: true },
    ],
    [
      'storage quota',
      {
        reserve: vi.fn(async () => Promise.reject(err(429, 'quota_exceeded', { kind: 'storage', used: 5, limit: 5 }))),
      },
      { reason: 'quota', retryable: false },
    ],
    [
      'document count quota',
      {
        reserve: vi.fn(async () =>
          Promise.reject(err(429, 'quota_exceeded', { kind: 'documents', used: 100, limit: 100 })),
        ),
      },
      { reason: 'quota', retryable: false },
    ],
    [
      'file too large',
      { reserve: vi.fn(async () => Promise.reject(err(413, 'file_too_large', { limit_mb: 50 }))) },
      { reason: 'too_large', retryable: false },
    ],
    [
      'too many pages',
      { reserve: vi.fn(async () => Promise.reject(err(422, 'too_many_pages', { limit: 1000 }))) },
      { reason: 'too_many_pages', retryable: false },
    ],
    [
      'not a pdf',
      { reserve: vi.fn(async () => Promise.reject(err(415, 'unsupported_type'))) },
      { reason: 'type', retryable: false },
    ],
    [
      'connection lost mid transfer',
      { send: vi.fn(async () => Promise.reject(Object.assign(new Error('net'), { status: 0 }))) },
      { reason: 'network', retryable: true },
    ],
    [
      'signed url refused',
      { send: vi.fn(async () => Promise.reject(Object.assign(new Error('403'), { status: 403 }))) },
      { reason: 'network', retryable: true },
    ],
    [
      'complete says not uploaded',
      { complete: vi.fn(async () => Promise.reject(err(409, 'not_uploaded'))) },
      { reason: 'network', retryable: true },
    ],
    [
      'rejected by the scan',
      { processing: vi.fn(async () => makeProcessing({ status: 'rejected', status_reason: 'malware' })) },
      { reason: 'scan_rejected', retryable: false },
    ],
    [
      'processing failed',
      { processing: vi.fn(async () => makeProcessing({ status: 'failed' })) },
      { reason: 'server', retryable: true },
    ],
  ]
  it.each(cases)('%s', async (_name, overrides, expected) => {
    const { manager, events, item } = setup(overrides)
    const id = manager.start(file(), { pages: null })
    await flush()
    expect(item(id)?.phase).toBe('failed')
    expect(item(id)?.failure).toMatchObject(expected)
    expect(events.at(-1)).toMatchObject({ type: 'failed' })
    expect(activeUploads(manager.getSnapshot())).toHaveLength(0)
  })

  it('keeps the request id on a server failure so support can find it', async () => {
    const { manager, item } = setup({
      reserve: vi.fn(async () => Promise.reject(err(500, 'internal', undefined, { request_id: 'req-9' }))),
    })
    const id = manager.start(file(), { pages: null })
    await flush()
    expect(item(id)?.failure?.requestId).toBe('req-9')
  })

  it('gives up polling after ten minutes without calling it a failed upload of the bytes', async () => {
    const { manager, item } = setup({ processing: vi.fn(async () => makeProcessing({ status: 'scanning' })) })
    const id = manager.start(file(), { pages: null })
    await flush()
    await vi.waitFor(() => expect(item(id)?.phase).toBe('failed'))
    expect(item(id)?.failure).toMatchObject({ retryable: false })
    expect(item(id)?.failure?.message).toMatch(/library soon/)
  })

  it('treats a lost connection while polling as "still checking"', async () => {
    const answers: Array<() => Promise<DocumentProcessing>> = [
      () => Promise.reject(Object.assign(new Error('net'), { status: 0 })),
      async () => makeProcessing(),
    ]
    const { manager, item } = setup({
      processing: vi.fn(async () => (answers.shift() as () => Promise<DocumentProcessing>)()),
    })
    const id = manager.start(file(), { pages: null })
    await flush()
    expect(item(id)?.phase).toBe('ready')
  })
})

describe('upload manager: retry, cancel and duplicates', () => {
  it('retries a failed upload with the same reservation inside 30 minutes', async () => {
    let first = true
    const { manager, deps, item } = setup({
      send: vi.fn(async (_t, f, o) => {
        if (first) {
          first = false
          throw Object.assign(new Error('net'), { status: 0 })
        }
        o.onProgress(f.size, f.size)
      }),
    })
    const id = manager.start(file(), { pages: null })
    await flush()
    expect(item(id)?.phase).toBe('failed')
    manager.retry(id)
    await flush()
    expect(item(id)?.phase).toBe('ready')
    expect(vi.mocked(deps.reserve).mock.calls.map(([b]) => b.client_id)).toEqual([id, id])
  })

  it('makes a new reservation when the old one has expired', async () => {
    let first = true
    const { manager, deps, item, advance } = setup({
      send: vi.fn(async (_t, f, o) => {
        if (first) {
          first = false
          throw Object.assign(new Error('net'), { status: 0 })
        }
        o.onProgress(f.size, f.size)
      }),
    })
    const id = manager.start(file(), { pages: null })
    await flush()
    advance(RESERVATION_MS + 1)
    manager.retry(id)
    await flush()
    expect(item(id)).toBeUndefined()
    expect(manager.getSnapshot()).toHaveLength(1)
    expect(manager.getSnapshot()[0]).toMatchObject({ id: 'id-2', phase: 'ready' })
    expect(vi.mocked(deps.reserve).mock.calls.map(([b]) => b.client_id)).toEqual(['id-1', 'id-2'])
  })

  it('does not retry what retrying cannot fix', async () => {
    const { manager, deps, item } = setup({
      reserve: vi.fn(async () => Promise.reject(err(413, 'file_too_large', { limit_mb: 50 }))),
    })
    const id = manager.start(file(), { pages: null })
    await flush()
    manager.retry(id)
    await flush()
    expect(deps.reserve).toHaveBeenCalledTimes(1)
    expect(item(id)?.phase).toBe('failed')
  })

  it('cancel stops the transfer, releases the reservation and removes the row', async () => {
    let signal: AbortSignal | undefined
    const { manager, deps } = setup({
      send: vi.fn((_t, _f, o) => {
        signal = o.signal
        return new Promise<void>(() => undefined)
      }),
    })
    const id = manager.start(file(), { pages: null })
    await flush()
    manager.cancel(id)
    expect(signal?.aborted).toBe(true)
    expect(deps.abort).toHaveBeenCalledWith(expect.any(String))
    expect(manager.getSnapshot()).toHaveLength(0)
  })

  it('offers a duplicate prompt, and "Open it" removes the new copy for good', async () => {
    const { manager, deps, item } = setup({ document: vi.fn(async () => makeDocument({ duplicate_of: 'orig-1' })) })
    const id = manager.start(file(), { pages: null })
    await flush()
    expect(item(id)).toMatchObject({ phase: 'duplicate', duplicateOf: 'orig-1' })
    await manager.discardDuplicate(id)
    expect(deps.purge).toHaveBeenCalled()
    expect(manager.getSnapshot()).toHaveLength(0)
  })

  it('"Keep both" turns the duplicate into a normal ready item', async () => {
    const { manager, item } = setup({ document: vi.fn(async () => makeDocument({ duplicate_of: 'orig-1' })) })
    const id = manager.start(file(), { pages: null })
    await flush()
    manager.keepBoth(id)
    expect(item(id)).toMatchObject({ phase: 'ready', duplicateOf: null })
  })

  it('dismiss removes a finished row, and unsubscribing stops notifications', async () => {
    const { manager } = setup()
    const listener = vi.fn()
    const off = manager.subscribe(listener)
    const id = manager.start(file(), { pages: null })
    await flush()
    off()
    listener.mockClear()
    manager.dismiss(id)
    expect(listener).not.toHaveBeenCalled()
    expect(manager.getSnapshot()).toHaveLength(0)
  })
})

describe('classifyUploadError and rejectionMessage', () => {
  it('maps 429 without a quota body to a wait message and a stale 409 on complete to retry', () => {
    expect(classifyUploadError(err(429, 'rate_limited'), 'reserve')).toMatchObject({
      reason: 'server',
      retryable: true,
    })
    expect(classifyUploadError(err(409, 'not_uploaded'), 'complete')).toMatchObject({
      reason: 'network',
      retryable: true,
    })
  })
  it('words each rejection reason in plain language', () => {
    for (const reason of ['malware', 'pdf_corrupt', 'type_mismatch', 'too_many_pages', 'too_large', null, 'x'])
      expect(rejectionMessage(reason)).toMatch(/could not accept this file/)
    expect(rejectionMessage('malware')).toMatch(/harmful/)
  })
})
