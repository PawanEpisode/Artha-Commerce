import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearOfflineQueue, resetFlushState, resetOfflineQueue } from '~/lib/offline-queue'

import {
  flushMarks,
  parkedMarkConflicts,
  queueMarkWrite,
  resetAnnotationQueue,
  resolveMarkConflict,
  waitingWrites,
} from './annotation-queue'
import { annotationScope, createBody, newMarkRecord, settleResults } from './annotation-sync'
import { DOC, makeAnnotation } from './annotation-testing'
import type { BatchOpBody, BatchResponse } from './annotation-types'
import type * as AnnotationsApi from './annotations-api'
import { batchMarks, putMark } from './annotations-api'

vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))
vi.mock('./annotations-api', async (original) => ({
  ...(await original<typeof AnnotationsApi>()),
  batchMarks: vi.fn(),
  putMark: vi.fn(),
}))

const NOW = '2026-10-08T10:00:00Z'
const draft = {
  kind: 'highlight' as const,
  page: 3,
  geometry: { quads: [[0.1, 0.1, 0.4, 0.02]] as [number, number, number, number][] },
  color: 'y' as const,
}
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const create = (n: number): BatchOpBody =>
  createBody(newMarkRecord(draft, { id: id(n), documentId: DOC, deviceId: 'd', now: NOW }))

const answerOk = (ops: BatchOpBody[]): BatchResponse => ({
  change_seq: ops.length,
  marks: { count: ops.length, limit: 20_000, near_limit: false },
  results: ops.map((op, i) => ({
    id: op.id,
    status: 'ok',
    annotation: makeAnnotation({ id: op.id, rev: 1, seq: i + 1 }),
  })),
})
const settleNothing = { settle: () => ({ conflicts: [], rejected: [] }) }

const sent = () => vi.mocked(batchMarks).mock.calls.map(([, ops]) => ops as BatchOpBody[])

beforeEach(async () => {
  resetOfflineQueue()
  resetFlushState()
  resetAnnotationQueue()
  await clearOfflineQueue()
  vi.mocked(batchMarks).mockReset()
  vi.mocked(putMark).mockReset()
  vi.mocked(batchMarks).mockImplementation(async (_doc, ops) => answerOk(ops))
  vi.unstubAllGlobals()
})

describe('offline marks, replayed in one batch', () => {
  it('sends 12 marks made offline in one request, in the order they were made, and nothing the second time', async () => {
    for (let n = 1; n <= 12; n++) await queueMarkWrite(DOC, id(n), { type: 'create', body: create(n) })
    expect(await waitingWrites(DOC)).toHaveLength(12)

    await flushMarks(DOC, settleNothing)
    expect(sent()).toHaveLength(1)
    expect(sent()[0]?.map((op) => op.id)).toEqual(Array.from({ length: 12 }, (_, i) => id(i + 1)))
    expect(await waitingWrites(DOC)).toHaveLength(0)

    await flushMarks(DOC, settleNothing)
    expect(sent()).toHaveLength(1)
  })

  it('splits a long queue into batches of 100 and keeps the order across them', async () => {
    for (let n = 1; n <= 250; n++) await queueMarkWrite(DOC, id(n), { type: 'create', body: create(n) })
    await flushMarks(DOC, settleNothing)
    expect(sent().map((ops) => ops.length)).toEqual([100, 100, 50])
    expect(
      sent()
        .flat()
        .map((op) => op.id),
    ).toEqual(Array.from({ length: 250 }, (_, i) => id(i + 1)))
  })

  it('folds an edit into the waiting create and sends nothing for a mark made and deleted offline', async () => {
    await queueMarkWrite(DOC, id(1), { type: 'create', body: create(1) })
    await queueMarkWrite(DOC, id(1), { type: 'edit', body: { op: 'upsert', id: id(1), base_rev: 1, comment: 'note' } })
    await queueMarkWrite(DOC, id(2), { type: 'create', body: create(2) })
    await queueMarkWrite(DOC, id(2), { type: 'delete', id: id(2), baseRev: 0 })
    const waiting = await waitingWrites(DOC)
    expect(waiting).toHaveLength(1)
    await flushMarks(DOC, settleNothing)
    expect(sent()[0]).toHaveLength(1)
    expect(sent()[0]?.[0]).toMatchObject({ id: id(1), comment: 'note', kind: 'highlight' })
    expect(sent()[0]?.[0]?.base_rev).toBeUndefined()
  })

  it('keeps everything, in order, when the network fails, and sends it later', async () => {
    for (let n = 1; n <= 3; n++) await queueMarkWrite(DOC, id(n), { type: 'create', body: create(n) })
    vi.mocked(batchMarks).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await flushMarks(DOC, settleNothing)
    expect(await waitingWrites(DOC)).toHaveLength(3)
    await flushMarks(DOC, settleNothing)
    expect(await waitingWrites(DOC)).toHaveLength(0)
    expect(
      sent()
        .at(-1)
        ?.map((op) => op.id),
    ).toEqual([id(1), id(2), id(3)])
  })

  it('does not fold a newer edit into a request that is out: it queues behind it', async () => {
    await queueMarkWrite(DOC, id(1), { type: 'create', body: create(1) })
    let release: () => void = () => undefined
    vi.mocked(batchMarks).mockImplementationOnce(
      (_doc, ops) => new Promise((resolve) => (release = () => resolve(answerOk(ops as BatchOpBody[])))),
    )
    const run = flushMarks(DOC, settleNothing)
    await vi.waitFor(() => expect(batchMarks).toHaveBeenCalled())
    const plan = await queueMarkWrite(DOC, id(1), {
      type: 'edit',
      body: { op: 'upsert', id: id(1), base_rev: 1, comment: 'later' },
    })
    expect(plan?.plan).toBe('enqueue')
    release()
    await run
    await flushMarks(DOC, settleNothing)
    expect(
      sent()
        .flat()
        .map((op) => op.comment),
    ).toEqual([undefined, 'later'])
  })
})

describe('conflicts', () => {
  it('parks a comment conflict on its own while the marks behind it go through, then settles it with the student’s choice', async () => {
    await queueMarkWrite(DOC, id(1), {
      type: 'edit',
      body: { op: 'upsert', id: id(1), base_rev: 1, comment: 'mine', base: { comment: 'old' } },
    })
    await queueMarkWrite(DOC, id(2), { type: 'edit', body: { op: 'upsert', id: id(2), base_rev: 1, color: 'g' } })
    const theirs = makeAnnotation({ id: id(1), comment: 'theirs', rev: 5 })
    const detail = { mine: { comment: 'mine' }, theirs, device_label: 'Pixel 7', theirs_updated_at: NOW }
    vi.mocked(batchMarks).mockResolvedValueOnce({
      change_seq: 9,
      results: [
        { id: id(1), status: 'conflict', error: { code: 'annotation_conflict', message: 'x', details: detail } },
        { id: id(2), status: 'ok', annotation: makeAnnotation({ id: id(2), color: 'g', rev: 2 }) },
      ],
    })
    let parkedCount = 0
    await flushMarks(DOC, {
      settle: ({ entries, results, stillWaiting }) => {
        const out = settleResults([], entries, results, stillWaiting, NOW)
        return { conflicts: out.conflicts, rejected: out.rejected }
      },
      onParked: () => (parkedCount += 1),
    })
    expect(await waitingWrites(DOC)).toHaveLength(0)
    expect(parkedCount).toBe(1)
    const parked = await parkedMarkConflicts(DOC)
    expect(parked).toHaveLength(1)
    expect(parked[0]?.detail.device_label).toBe('Pixel 7')

    vi.mocked(putMark).mockResolvedValueOnce({ annotation: makeAnnotation({ id: id(1), rev: 6 }), change_seq: 10 })
    await resolveMarkConflict(parked[0] as NonNullable<(typeof parked)[number]>, 'both')
    expect(putMark).toHaveBeenCalledWith(
      expect.objectContaining({ id: id(1), base_rev: 5, resolution: 'both', comment: 'mine' }),
    )
    expect(await parkedMarkConflicts(DOC)).toHaveLength(0)
  })
})

describe('one flusher per account', () => {
  it('takes the Web Locks lock named for the account and this document, and sends nothing when another tab holds it', async () => {
    await queueMarkWrite(DOC, id(1), { type: 'create', body: create(1) })
    const request = vi.fn(async (_name: string, _options: unknown, callback: (lock: null) => Promise<unknown>) =>
      callback(null),
    )
    vi.stubGlobal('navigator', { locks: { request } })
    const result = await flushMarks(DOC, settleNothing)
    expect(request).toHaveBeenCalledWith(
      `artha-flush:u1:${annotationScope(DOC)}`,
      { ifAvailable: true },
      expect.any(Function),
    )
    expect(result?.busy).toBe(true)
    expect(batchMarks).not.toHaveBeenCalled()
    expect(await waitingWrites(DOC)).toHaveLength(1)
  })

  it('lets two flushes in the same tab share one run, so a mark is never sent twice', async () => {
    for (let n = 1; n <= 5; n++) await queueMarkWrite(DOC, id(n), { type: 'create', body: create(n) })
    await Promise.all([flushMarks(DOC, settleNothing), flushMarks(DOC, settleNothing)])
    expect(sent().flat()).toHaveLength(5)
  })
})
