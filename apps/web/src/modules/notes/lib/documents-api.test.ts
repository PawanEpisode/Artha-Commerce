import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  abortDocument,
  completeDocument,
  createArchiveExport,
  createDocumentExport,
  deleteDocument,
  getDocument,
  getExport,
  getPagesText,
  getProcessing,
  listDocuments,
  patchDocument,
  putProgress,
  putRanges,
  reserveDocument,
  restoreDocument,
  searchDocument,
  startOcr,
} from './documents-api'

const ID = '11111111-1111-4111-8111-111111111111'
let fetchMock: ReturnType<typeof vi.fn>

const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const lastCall = () => {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit]
  const parsed = new URL(url)
  return {
    path: parsed.pathname.replace('/api/v1', ''),
    query: Object.fromEntries(parsed.searchParams),
    method: init.method ?? 'GET',
    body: init.body ? JSON.parse(init.body as string) : undefined,
    init,
  }
}

beforeEach(() => {
  fetchMock = vi.fn(async () => reply({}))
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

describe('document endpoints', () => {
  it('reserves, completes and aborts an upload', async () => {
    const body = { client_id: ID, filename: 'a.pdf', bytes: 10, mime: 'application/pdf' as const }
    await reserveDocument(body)
    expect(lastCall()).toMatchObject({ path: '/notes/documents/', method: 'POST', body })
    await completeDocument(ID)
    expect(lastCall()).toMatchObject({ path: `/notes/documents/${ID}/complete/`, method: 'POST' })
    await abortDocument(ID)
    expect(lastCall()).toMatchObject({ path: `/notes/documents/${ID}/abort/`, method: 'POST' })
  })

  it('lists with filters and skips empty ones', async () => {
    await listDocuments({ subject: 'taxation', status: 'ready', limit: 3, q: '', trashed: false, sort: 'recent' })
    expect(lastCall()).toMatchObject({
      path: '/notes/documents/',
      method: 'GET',
      query: { subject: 'taxation', status: 'ready', limit: '3', sort: 'recent' },
    })
    await listDocuments({ trashed: true, cursor: 'abc' })
    expect(lastCall().query).toEqual({ trashed: '1', cursor: 'abc' })
    await listDocuments()
    expect(lastCall().query).toEqual({})
  })

  it('gets, patches, trashes, purges and restores one document', async () => {
    await getDocument(ID)
    expect(lastCall()).toMatchObject({ path: `/notes/documents/${ID}/`, method: 'GET' })
    await patchDocument(ID, { base_rev: 2, title: 'New' })
    expect(lastCall()).toMatchObject({ method: 'PATCH', body: { base_rev: 2, title: 'New' } })
    await deleteDocument(ID)
    expect(lastCall()).toMatchObject({ method: 'DELETE', query: {} })
    await deleteDocument(ID, true)
    expect(lastCall()).toMatchObject({ method: 'DELETE', query: { permanent: '1' } })
    await restoreDocument(ID)
    expect(lastCall()).toMatchObject({ path: `/notes/documents/${ID}/restore/`, method: 'POST' })
  })

  it('replaces page ranges', async () => {
    const ranges = [{ page_from: 1, page_to: 10, chapter_id: 'c1' }]
    await putRanges(ID, ranges)
    expect(lastCall()).toMatchObject({ path: `/notes/documents/${ID}/chapters/`, method: 'PUT', body: { ranges } })
  })

  it('saves progress, with keepalive for a closing page', async () => {
    await putProgress(ID, { last_page: 142, last_zoom: 'fit', page_tone: 'night' })
    expect(lastCall()).toMatchObject({
      path: `/notes/documents/${ID}/progress/`,
      method: 'PUT',
      body: { last_page: 142, last_zoom: 'fit', page_tone: 'night' },
    })
    expect(lastCall().init.keepalive).toBeUndefined()
    await putProgress(ID, { last_page: 1, last_zoom: '125' }, { keepalive: true })
    expect(lastCall().init.keepalive).toBe(true)
  })

  it('reads processing, page text and search', async () => {
    await getProcessing(ID)
    expect(lastCall()).toMatchObject({ path: `/notes/documents/${ID}/processing/` })
    await getPagesText(ID, 21, 40)
    expect(lastCall()).toMatchObject({ path: `/notes/documents/${ID}/pages/text/`, query: { from: '21', to: '40' } })
    await searchDocument(ID, 'ITC')
    expect(lastCall()).toMatchObject({ path: `/notes/documents/${ID}/search/`, query: { q: 'ITC', limit: '50' } })
    await searchDocument(ID, 'Ind AS 115', 10)
    expect(lastCall().query).toEqual({ q: 'Ind AS 115', limit: '10' })
  })

  it('starts OCR and exports', async () => {
    await startOcr(ID, { mode: 'tesseract', lang: 'eng+hin', pages: '1-40' })
    expect(lastCall()).toMatchObject({
      path: `/notes/documents/${ID}/ocr/`,
      method: 'POST',
      body: { mode: 'tesseract', lang: 'eng+hin', pages: '1-40' },
    })
    await createDocumentExport(ID, { client_id: ID, options: { pages: '1-5', include: ['highlight'] } })
    expect(lastCall()).toMatchObject({
      path: `/notes/documents/${ID}/exports/`,
      method: 'POST',
      body: { client_id: ID, options: { pages: '1-5', include: ['highlight'] } },
    })
    await createArchiveExport(ID)
    expect(lastCall()).toMatchObject({ path: '/notes/export/archive/', method: 'POST', body: { client_id: ID } })
    await getExport(ID)
    expect(lastCall()).toMatchObject({ path: `/notes/exports/${ID}/`, method: 'GET' })
  })

  it('escapes ids and surfaces API errors with their envelope', async () => {
    await getDocument('a/b')
    expect(lastCall().path).toBe('/notes/documents/a%2Fb/')
    fetchMock.mockResolvedValueOnce(reply({ error: { code: 'file_too_large', details: { limit_mb: 50 } } }, 413))
    await expect(
      reserveDocument({ client_id: ID, filename: 'a.pdf', bytes: 9e9, mime: 'application/pdf' }),
    ).rejects.toMatchObject({ status: 413, code: 'file_too_large' })
  })
})
