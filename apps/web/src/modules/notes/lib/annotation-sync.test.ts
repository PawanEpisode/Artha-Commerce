import { describe, expect, it } from 'vitest'

import {
  applyBody,
  applyPending,
  batchesOf,
  createBody,
  deleteBody,
  editBody,
  foldUpsert,
  localMarksInfo,
  mergeDelta,
  needsFullResync,
  newMarkRecord,
  planWrite,
  pruneTombstones,
  replaceWithSnapshot,
  resolutionBody,
  settleResults,
  sortMarks,
} from './annotation-sync'
import { DOC, entry, makeAnnotation, makeMark } from './annotation-testing'

const NOW = '2026-10-08T10:00:00Z'
const ID = '11111111-1111-4111-8111-111111111111'
const draft = {
  kind: 'highlight' as const,
  page: 3,
  geometry: { quads: [[0.1, 0.1, 0.4, 0.02]] as [number, number, number, number][] },
  color: 'y' as const,
}

describe('bodies', () => {
  it('makes a create without base_rev and an edit with only what changed and what was seen', () => {
    const mark = newMarkRecord(draft, { id: ID, documentId: DOC, deviceId: 'd', now: NOW })
    expect(createBody(mark)).toMatchObject({ op: 'upsert', id: ID, kind: 'highlight', page: 3, device_id: 'd' })
    expect(createBody(mark).base_rev).toBeUndefined()
    const edit = editBody({ id: ID, document_id: DOC, rev: 4 }, { comment: 'new' }, { comment: 'old' })
    expect(edit).toEqual({
      op: 'upsert',
      id: ID,
      document_id: DOC,
      base_rev: 4,
      comment: 'new',
      base: { comment: 'old' },
    })
  })

  it('leaves base_rev out of a delete for a mark the server has not confirmed', () => {
    expect(deleteBody(ID, 0)).toEqual({ op: 'delete', id: ID })
    expect(deleteBody(ID, 3)).toEqual({ op: 'delete', id: ID, base_rev: 3 })
  })

  it('folds edits: newest value wins, oldest seen value and base_rev stay', () => {
    const first = editBody({ id: ID, document_id: DOC, rev: 2 }, { comment: 'a' }, { comment: 'server' })
    const second = editBody(
      { id: ID, document_id: DOC, rev: 3 },
      { comment: 'b', color: 'g' },
      { comment: 'a', color: 'y' },
    )
    const folded = foldUpsert(first, second)
    expect(folded).toMatchObject({ base_rev: 2, comment: 'b', color: 'g', base: { comment: 'server', color: 'y' } })
  })
})

describe('planWrite: what a local action does to what already waits for the same mark', () => {
  const created = entry(
    createBody(newMarkRecord(draft, { id: ID, documentId: DOC, deviceId: 'd', now: NOW })),
    'create',
  )

  it('queues a first write', () => {
    expect(planWrite([], { type: 'edit', body: { op: 'upsert', id: ID, base_rev: 1, comment: 'x' } }).action).toBe(
      'enqueue',
    )
  })

  it('folds an edit into the create that is still waiting, keeping its place in line', () => {
    const plan = planWrite([created], { type: 'edit', body: { op: 'upsert', id: ID, base_rev: 1, comment: 'x' } })
    expect(plan).toMatchObject({ action: 'replace', clientId: 'create', body: { comment: 'x', kind: 'highlight' } })
    expect((plan as { body: { base_rev?: number } }).body.base_rev).toBeUndefined()
  })

  it('cancels a mark made and deleted offline: nothing is sent', () => {
    expect(planWrite([created], { type: 'delete', id: ID, baseRev: 0 })).toEqual({
      action: 'cancel',
      clientIds: ['create'],
    })
  })

  it('turns a waiting edit plus a delete into one delete (the edit would be lost anyway)', () => {
    const edit = entry({ op: 'upsert', id: ID, base_rev: 4, comment: 'x' }, 'edit')
    expect(planWrite([edit], { type: 'delete', id: ID, baseRev: 4 })).toMatchObject({
      action: 'replace',
      clientId: 'edit',
      body: { op: 'delete', base_rev: 4 },
    })
  })

  it('does not fold an edit behind a delete: order is kept (delete, then the edit that beats it)', () => {
    const del = entry({ op: 'delete', id: ID, base_rev: 4 }, 'del')
    expect(planWrite([del], { type: 'edit', body: { op: 'upsert', id: ID, base_rev: 4, comment: 'x' } }).action).toBe(
      'enqueue',
    )
  })

  it('cancels a delete that is undone before it was sent, and recreates a mark whose create was cancelled', () => {
    const del = entry({ op: 'delete', id: ID, base_rev: 4 }, 'del')
    expect(planWrite([del], { type: 'restore', id: ID })).toEqual({ action: 'cancel', clientIds: ['del'] })
    const recreate = createBody(newMarkRecord(draft, { id: ID, documentId: DOC, deviceId: 'd', now: NOW }))
    expect(planWrite([], { type: 'restore', id: ID, recreate })).toEqual({ action: 'enqueue', body: recreate })
    expect(planWrite([], { type: 'restore', id: ID })).toEqual({ action: 'enqueue', body: { op: 'restore', id: ID } })
  })

  it('replays offline create, edit and delete of different marks in the order they were made', () => {
    // Folding only ever touches the same mark, so two marks keep their order of creation.
    const a = entry({ op: 'upsert', id: 'a', document_id: DOC, kind: 'highlight', page: 1, geometry: {} }, 'a')
    const b = entry({ op: 'upsert', id: 'b', document_id: DOC, kind: 'highlight', page: 2, geometry: {} }, 'b')
    expect(a.queuedAt).toBeLessThan(b.queuedAt)
    const plan = planWrite([a], { type: 'edit', body: { op: 'upsert', id: 'a', base_rev: 1, comment: 'x' } })
    expect(plan).toMatchObject({ action: 'replace', clientId: 'a' })
  })
})

describe('applying writes to the local copy', () => {
  it('shows an edit at once and clears a deletion (edit beats delete)', () => {
    const gone = makeMark({ deleted_at: NOW })
    expect(applyBody(gone, { op: 'upsert', id: ID, base_rev: 1, comment: 'x' }, NOW)?.deleted_at).toBeNull()
    expect(applyBody(makeMark(), { op: 'delete', id: ID }, NOW)?.deleted_at).toBe(NOW)
  })

  it('rebuilds a reloaded screen from the cache plus the waiting writes, once however often it is replayed', () => {
    const waiting = [
      entry(createBody(newMarkRecord(draft, { id: 'n1', documentId: DOC, deviceId: 'd', now: NOW }))),
      entry({ op: 'upsert', id: ID, base_rev: 1, comment: 'edited' }),
    ]
    const once = applyPending([makeMark()], waiting, NOW)
    const twice = applyPending(once, waiting, NOW)
    expect(twice).toHaveLength(2)
    expect(twice.find((m) => m.id === ID)?.comment).toBe('edited')
    expect(twice.find((m) => m.id === 'n1')?.local_only).toBe(true)
  })
})

describe('settleResults', () => {
  const ok = (annotation = makeAnnotation(), extra: object = {}) => ({
    id: annotation.id,
    status: 'ok' as const,
    annotation,
    ...extra,
  })

  it('applies answers and keeps later waiting writes on top of the server version', () => {
    const sent = [entry({ op: 'upsert', id: ID, base_rev: 1, comment: 'a' })]
    const later = [entry({ op: 'upsert', id: ID, base_rev: 2, comment: 'b' })]
    const out = settleResults(
      [makeMark({ comment: 'a' })],
      sent,
      [ok(makeAnnotation({ rev: 2, comment: 'a' }))],
      later,
      NOW,
    )
    expect(out.accepted).toBe(1)
    expect(out.marks[0]).toMatchObject({ rev: 2, comment: 'b' })
  })

  it('counts a delete that lost to a newer edit elsewhere', () => {
    const sent = [entry({ op: 'delete', id: ID, base_rev: 1 })]
    const out = settleResults(
      [makeMark({ deleted_at: NOW })],
      sent,
      [ok(makeAnnotation({ rev: 3 }), { edit_wins: true })],
      [],
      NOW,
    )
    expect(out.editWins).toBe(1)
    expect(out.marks[0]?.deleted_at).toBeNull()
  })

  it('parks a conflict without blocking the others in the same batch', () => {
    const a = entry({ op: 'upsert', id: 'a', base_rev: 1, comment: 'mine' })
    const b = entry({ op: 'upsert', id: 'b', base_rev: 1, color: 'g' })
    const detail = {
      mine: { comment: 'mine' },
      theirs: makeAnnotation({ id: 'a', comment: 'theirs', rev: 2 }),
      device_label: 'Pixel',
      theirs_updated_at: NOW,
    }
    const out = settleResults(
      [makeMark({ id: 'a' }), makeMark({ id: 'b' })],
      [a, b],
      [
        { id: 'a', status: 'conflict', error: { code: 'annotation_conflict', message: 'x', details: detail } },
        ok(makeAnnotation({ id: 'b', color: 'g', rev: 2 })),
      ],
      [],
      NOW,
    )
    expect(out.conflicts).toHaveLength(1)
    expect(out.conflicts[0]?.detail.device_label).toBe('Pixel')
    expect(out.accepted).toBe(1)
    expect(out.marks.find((m) => m.id === 'b')?.color).toBe('g')
  })

  it('drops a refused create from the screen and asks for a resync after a refused edit', () => {
    const create = entry({ op: 'upsert', id: 'a', document_id: DOC, kind: 'ink', page: 1, geometry: {} })
    const edit = entry({ op: 'upsert', id: 'b', base_rev: 1, comment: 'x' })
    const rejected = (id: string) => ({
      id,
      status: 'rejected' as const,
      error: { code: 'invalid_geometry', message: 'bad' },
    })
    const out = settleResults(
      [makeMark({ id: 'a' }), makeMark({ id: 'b' })],
      [create, edit],
      [rejected('a'), rejected('b')],
      [],
      NOW,
    )
    expect(out.marks.map((m) => m.id)).toEqual(['b'])
    expect(out.needsResync).toBe(true)
    expect(out.rejected).toHaveLength(2)
  })
})

describe('delta feed', () => {
  it('merges changed rows, tombstones included, and keeps a waiting edit on top', () => {
    const local = [makeMark({ id: 'a' }), makeMark({ id: 'b' })]
    const items = [
      makeAnnotation({ id: 'a', rev: 2, comment: 'elsewhere' }),
      makeAnnotation({ id: 'b', rev: 2, deleted_at: NOW }),
    ]
    const out = mergeDelta(local, items, [entry({ op: 'upsert', id: 'a', base_rev: 1, comment: 'mine' })], NOW)
    expect(out.find((m) => m.id === 'a')?.comment).toBe('mine')
    expect(out.find((m) => m.id === 'b')?.deleted_at).toBe(NOW)
  })

  it('resyncs from 0 after a month away, and keeps marks that only exist here', () => {
    const day = 86_400_000
    expect(needsFullResync(null, 0)).toBe(true)
    expect(needsFullResync(0, 10 * day)).toBe(false)
    expect(needsFullResync(0, 30 * day)).toBe(true)
    const snapshot = replaceWithSnapshot(
      [makeAnnotation({ id: 'a' })],
      [entry(createBody(newMarkRecord(draft, { id: 'n1', documentId: DOC, deviceId: 'd', now: NOW })))],
      NOW,
    )
    expect(snapshot.map((m) => m.id).sort()).toEqual(['a', 'n1'])
  })

  it('prunes tombstones after 30 days, and drops marks deleted before the server ever saw them', () => {
    const now = Date.parse('2026-10-08T00:00:00Z')
    const marks = [
      makeMark({ id: 'old', deleted_at: '2026-08-01T00:00:00Z' }),
      makeMark({ id: 'recent', deleted_at: '2026-10-01T00:00:00Z' }),
      makeMark({ id: 'never', deleted_at: '2026-10-07T00:00:00Z', local_only: true }),
      makeMark({ id: 'live' }),
    ]
    expect(pruneTombstones(marks, now).map((m) => m.id)).toEqual(['recent', 'live'])
  })
})

describe('batches, order and resolution', () => {
  it('splits into groups of at most 100 in order', () => {
    const rows = Array.from({ length: 250 }, (_, i) => i)
    const groups = batchesOf(rows)
    expect(groups.map((g) => g.length)).toEqual([100, 100, 50])
    expect(groups.flat()).toEqual(rows)
  })

  it('reads in page order, then top to bottom', () => {
    const a = makeMark({ id: 'a', page: 2, geometry: { quads: [[0.1, 0.5, 0.2, 0.02]] } })
    const b = makeMark({ id: 'b', page: 2, geometry: { quads: [[0.1, 0.1, 0.2, 0.02]] } })
    const c = makeMark({ id: 'c', page: 1, geometry: { quads: [[0.1, 0.9, 0.2, 0.02]] } })
    expect(sortMarks([a, b, c]).map((m) => m.id)).toEqual(['c', 'b', 'a'])
  })

  it('resolves a conflict on the stored revision with the student’s choice', () => {
    const parked = { op: 'upsert', id: ID, base_rev: 1, comment: 'mine', base: { comment: 'old' } } as const
    expect(resolutionBody(parked, makeAnnotation({ rev: 5, comment: 'theirs' }), 'both')).toEqual({
      op: 'upsert',
      id: ID,
      base_rev: 5,
      comment: 'mine',
      base: { comment: 'theirs' },
      resolution: 'both',
    })
  })

  it('counts marks against the plan’s cap and flags 95%', () => {
    expect(localMarksInfo(10)).toMatchObject({ count: 10, near_limit: false })
    expect(localMarksInfo(19_000, { count: 0, limit: 20_000, near_limit: false }).near_limit).toBe(true)
  })
})
