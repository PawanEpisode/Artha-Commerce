/**
 * The pure core of annotation sync (ERD decision 9, section 3.6): how a local action becomes a queue entry, how entries
 * fold together while they wait, how a batch answer and a delta page change the local copy. No React, no IndexedDB, no
 * network: `annotation-queue.ts` does the IO and calls these. Ordering rule: entries replay in the order they were made;
 * an edit folds into the waiting write of the same mark only while that write is the mark's latest (so it never jumps
 * behind a delete or a restore queued after it).
 */
import type {
  Annotation,
  AnnotationConflictDetail,
  BatchError,
  BatchOpBody,
  BatchResultItem,
  MarkDraft,
  MarkFields,
  MarkPatch,
  MarkRecord,
  MarksInfo,
  Resolution,
} from './annotation-types'
import { geometryBbox } from './geometry'
import type { NoteLink } from './types'

/** Plan's cap of marks per document (PRD 7.3) until a write response says otherwise. */
export const DEFAULT_MARKS_LIMIT = 20_000
/** The API keeps tombstones this long; a device that has not synced for longer starts from `since_seq=0`. */
export const TOMBSTONE_DAYS = 30
const DAY_MS = 86_400_000
/** One day of slack, so a device that is exactly at the edge resyncs rather than misses a purged delete. */
export const RESYNC_AFTER_MS = (TOMBSTONE_DAYS - 1) * DAY_MS

export const UNFILED: NoteLink = {
  level_id: null,
  subject_id: null,
  subject_key: null,
  subject_name: null,
  chapter_id: null,
  chapter_key: null,
  chapter_name: null,
  topic_id: null,
  topic_key: null,
  topic_name: null,
  moved_or_removed: false,
}

/** The lane of one document's writes in the shared queue: documents never wait on each other. */
export const annotationScope = (documentId: string) => `notes-ann:${documentId}`
export const isAnnotationScope = (scope: string) => scope.startsWith('notes-ann:')
export const documentOfScope = (scope: string) => scope.slice('notes-ann:'.length)

/** The minimal shape of a queue entry this file reads (`QueuedWrite` satisfies it). */
export interface EntryLike {
  clientId: string
  body: Record<string, unknown>
  queuedAt: number
}
export const bodyOf = (entry: EntryLike) => entry.body as BatchOpBody
export const entryMarkId = (entry: EntryLike) => bodyOf(entry).id
export const isCreateBody = (body: BatchOpBody) => body.op === 'upsert' && !body.base_rev
export const isEditBody = (body: BatchOpBody) => body.op === 'upsert' && !!body.base_rev

// ---- Bodies ---------------------------------------------------------------------------------------------------------

const FIELD_KEYS = [
  'page',
  'geometry',
  'color',
  'comment',
  'quote_exact',
  'quote_prefix',
  'quote_suffix',
  'text_start',
  'text_end',
  'anchor_engine',
  'chapter_id',
  'topic_id',
  'tag_ids',
] as const satisfies ReadonlyArray<keyof MarkFields>

/** Fields whose last-seen value travels as `base` (the server compares it, ERD 3.6). Geometry and tags are last write wins. */
const BASED_FIELDS = ['page', 'color', 'comment', 'chapter_id', 'topic_id'] as const

/** A new mark's PUT body: no `base_rev`, so the server creates (or returns the stored row for a replay). */
export function createBody(
  mark: MarkRecord,
  extra: { chapter_id?: string | null; topic_id?: string | null; tag_ids?: string[] } = {},
): BatchOpBody {
  const body: BatchOpBody = {
    op: 'upsert',
    id: mark.id,
    document_id: mark.document_id,
    kind: mark.kind,
    page: mark.page,
    geometry: mark.geometry,
    device_id: mark.device_id,
  }
  if (mark.color) body.color = mark.color
  if (mark.comment) body.comment = mark.comment
  for (const key of ['quote_exact', 'quote_prefix', 'quote_suffix', 'anchor_engine'] as const)
    if (mark[key]) body[key] = mark[key]
  for (const key of ['text_start', 'text_end'] as const) if (mark[key] !== null) body[key] = mark[key]
  if (extra.chapter_id) body.chapter_id = extra.chapter_id
  if (extra.topic_id) body.topic_id = extra.topic_id
  if (extra.tag_ids?.length) body.tag_ids = extra.tag_ids
  return body
}

/** The edit's body: only what changed, each based field with the value the student last saw. */
export function editBody(
  mark: Pick<MarkRecord, 'id' | 'document_id' | 'rev'> & Partial<MarkFields>,
  patch: MarkPatch,
  seen: Partial<MarkFields>,
): BatchOpBody {
  const body: BatchOpBody = { op: 'upsert', id: mark.id, document_id: mark.document_id, base_rev: mark.rev }
  const base: Record<string, unknown> = {}
  for (const key of FIELD_KEYS) {
    if (!(key in patch)) continue
    body[key] = patch[key]
    if ((BASED_FIELDS as readonly string[]).includes(key)) base[key] = seen[key] ?? null
  }
  if (Object.keys(base).length > 0) body.base = base
  return body
}

/** `base_rev` is left out for a mark that has no revision yet (its create is still out): the delete is then unconditional. */
export const deleteBody = (id: string, baseRev: number): BatchOpBody =>
  baseRev > 0 ? { op: 'delete', id, base_rev: baseRev } : { op: 'delete', id }
export const restoreBody = (id: string): BatchOpBody => ({ op: 'restore', id })

/** Folds a newer edit into a waiting upsert: newer fields win, the oldest `base_rev` and the oldest seen values stay. */
export function foldUpsert(waiting: BatchOpBody, next: BatchOpBody): BatchOpBody {
  const { resolution: _old, ...rest } = waiting
  const merged: BatchOpBody = { ...rest }
  for (const [key, value] of Object.entries(next)) {
    if (key === 'op' || key === 'id' || key === 'base_rev' || key === 'base') continue
    merged[key] = value
  }
  if (waiting.base !== undefined || next.base !== undefined) {
    merged.base = { ...(next.base as object | undefined), ...(waiting.base as object | undefined) }
  }
  return merged
}

// ---- The planner: one local action against what already waits for the same mark --------------------------------------

export type LocalOp =
  | { type: 'create'; body: BatchOpBody }
  | { type: 'edit'; body: BatchOpBody }
  | { type: 'delete'; id: string; baseRev: number }
  /** `recreate` is the create body of a mark that never reached the server (its create was cancelled by a delete): Undo makes it again. */
  | { type: 'restore'; id: string; recreate?: BatchOpBody }

export type Plan =
  /** A new entry at the end of the queue. */
  | { action: 'enqueue'; body: BatchOpBody }
  /** The waiting entry changes in place and keeps its place in line. */
  | { action: 'replace'; clientId: string; body: BatchOpBody }
  /** Nothing needs sending: these waiting entries cancel out (a mark made and deleted offline, a delete undone). */
  | { action: 'cancel'; clientIds: string[] }

/** `waiting` is every queued entry of this one mark, in queue order. */
export function planWrite(waiting: readonly EntryLike[], op: LocalOp): Plan {
  const last = waiting[waiting.length - 1]
  const lastBody = last ? bodyOf(last) : undefined
  switch (op.type) {
    case 'create':
      return { action: 'enqueue', body: op.body }
    case 'edit':
      if (last && lastBody?.op === 'upsert')
        return { action: 'replace', clientId: last.clientId, body: foldUpsert(lastBody, op.body) }
      return { action: 'enqueue', body: op.body }
    case 'delete':
      if (last && lastBody && isCreateBody(lastBody) && waiting.length === 1)
        return { action: 'cancel', clientIds: waiting.map((e) => e.clientId) }
      if (last && lastBody && isEditBody(lastBody))
        return { action: 'replace', clientId: last.clientId, body: deleteBody(op.id, lastBody.base_rev as number) }
      return { action: 'enqueue', body: deleteBody(op.id, op.baseRev) }
    case 'restore':
      if (last && lastBody?.op === 'delete') return { action: 'cancel', clientIds: [last.clientId] }
      if (waiting.length === 0 && op.recreate) return { action: 'enqueue', body: op.recreate }
      return { action: 'enqueue', body: restoreBody(op.id) }
  }
}

// ---- Local copy ------------------------------------------------------------------------------------------------------

/** Builds the local record of a new mark. Everything the server will add (link, rev, seq) starts neutral. */
export function newMarkRecord(
  draft: MarkDraft,
  ctx: {
    id: string
    documentId: string
    deviceId: string | null
    now: string
    link?: NoteLink
    tags?: Annotation['tags']
  },
): MarkRecord {
  return {
    id: ctx.id,
    document_id: ctx.documentId,
    page: draft.page,
    kind: draft.kind,
    geometry: draft.geometry,
    color: draft.color ?? null,
    comment: draft.comment ?? '',
    quote_exact: draft.quote_exact ?? null,
    quote_prefix: draft.quote_prefix ?? null,
    quote_suffix: draft.quote_suffix ?? null,
    text_start: draft.text_start ?? null,
    text_end: draft.text_end ?? null,
    anchor_engine: draft.anchor_engine ?? null,
    link: ctx.link ?? UNFILED,
    chapter_source: 'none',
    tags: ctx.tags ?? [],
    recall_card_id: null,
    rev: 0,
    seq: 0,
    device_id: ctx.deviceId,
    created_at: ctx.now,
    updated_at: ctx.now,
    deleted_at: null,
    local_only: true,
  }
}

const LOCAL_FIELDS = [
  'page',
  'geometry',
  'color',
  'comment',
  'quote_exact',
  'quote_prefix',
  'quote_suffix',
  'text_start',
  'text_end',
  'anchor_engine',
] as const

/** Applies one queued write to the local copy of its mark (what the student already sees). Idempotent. */
export function applyBody(mark: MarkRecord | undefined, body: BatchOpBody, now: string): MarkRecord | undefined {
  if (body.op === 'upsert') {
    if (!mark) {
      if (!body.kind || !body.document_id) return undefined
      const made = newMarkRecord(
        {
          kind: body.kind as MarkRecord['kind'],
          page: body.page as number,
          geometry: body.geometry as MarkRecord['geometry'],
        },
        { id: body.id, documentId: body.document_id, deviceId: (body.device_id as string | null) ?? null, now },
      )
      return applyBody(made, { ...body, op: 'upsert' }, now) ?? made
    }
    const next: MarkRecord = { ...mark }
    for (const key of LOCAL_FIELDS) if (key in body) (next as unknown as Record<string, unknown>)[key] = body[key]
    next.updated_at = now
    // Edit beats delete (ERD 3.6): the server brings a deleted mark back when this edit arrives.
    if (isEditBody(body)) next.deleted_at = null
    return next
  }
  if (!mark) return undefined
  if (body.op === 'delete') return { ...mark, deleted_at: now, updated_at: now }
  return { ...mark, deleted_at: null, updated_at: now }
}

/** The local copy rebuilt from what the server last said plus the writes still waiting (after a reload, or a delta page). */
export function applyPending(marks: readonly MarkRecord[], entries: readonly EntryLike[], now: string): MarkRecord[] {
  const byId = new Map(marks.map((m) => [m.id, m]))
  for (const entry of entries) {
    const body = bodyOf(entry)
    const applied = applyBody(byId.get(body.id), body, now)
    if (applied) byId.set(body.id, applied)
  }
  return [...byId.values()]
}

/** Reading order: page, then top of the mark, then left edge. Stable for equal marks (creation time, id). */
export function sortMarks<T extends Pick<MarkRecord, 'page' | 'kind' | 'geometry' | 'created_at' | 'id'>>(
  marks: readonly T[],
): T[] {
  const key = (m: T) => {
    const [x, y] = geometryBbox(m.kind, m.geometry)
    return [m.page, y, x] as const
  }
  return [...marks].sort((a, b) => {
    const [pa, ya, xa] = key(a)
    const [pb, yb, xb] = key(b)
    return pa - pb || ya - yb || xa - xb || a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)
  })
}

export const liveMarks = <T extends Pick<MarkRecord, 'deleted_at'>>(marks: readonly T[]): T[] =>
  marks.filter((m) => m.deleted_at === null)

// ---- Delta feed --------------------------------------------------------------------------------------------------------

/** True when this device has not synced for so long that the API may have purged tombstones it never saw. */
export const needsFullResync = (syncedAt: number | null | undefined, now: number): boolean =>
  syncedAt === null || syncedAt === undefined || now - syncedAt > RESYNC_AFTER_MS

/**
 * Merges delta rows into the local copy, in `seq` order. A mark with writes still waiting keeps those writes on top of
 * the server's version (they will reach the server and be reconciled there), so the student never sees their own
 * pending change flicker back.
 */
export function mergeDelta(
  marks: readonly MarkRecord[],
  items: readonly Annotation[],
  waiting: readonly EntryLike[],
  now: string,
): MarkRecord[] {
  const byId = new Map(marks.map((m) => [m.id, m]))
  const waitingBy = groupByMark(waiting)
  for (const item of items) {
    const base: MarkRecord = { ...item }
    const pending = waitingBy.get(item.id)
    byId.set(item.id, pending ? overlay(base, pending, now) : base)
  }
  return [...byId.values()]
}

/** A snapshot from `since_seq=0`: the server's marks replace the cache; marks that only exist here (waiting creates) stay. */
export function replaceWithSnapshot(
  items: readonly Annotation[],
  waiting: readonly EntryLike[],
  now: string,
): MarkRecord[] {
  return applyPending(items, waiting, now)
}

function overlay(base: MarkRecord, entries: readonly EntryLike[], now: string): MarkRecord {
  let mark: MarkRecord | undefined = base
  for (const entry of entries) mark = applyBody(mark, bodyOf(entry), now)
  return mark ?? base
}

/** Tombstones past the API's purge are dropped from the cache. */
export function pruneTombstones(marks: readonly MarkRecord[], now: number): MarkRecord[] {
  // A mark deleted before it ever reached the server is not a tombstone anyone needs: it never existed there.
  return marks.filter(
    (m) => !m.deleted_at || (!m.local_only && now - new Date(m.deleted_at).getTime() <= TOMBSTONE_DAYS * DAY_MS),
  )
}

export function groupByMark<T extends EntryLike>(entries: readonly T[]): Map<string, T[]> {
  const out = new Map<string, T[]>()
  for (const e of entries) {
    const id = entryMarkId(e)
    out.set(id, [...(out.get(id) ?? []), e])
  }
  return out
}

// ---- Batches and their answers -------------------------------------------------------------------------------------------

/** Consecutive entries in groups of at most `max`, order kept: one request each. */
export function batchesOf<T>(entries: readonly T[], max = 100): T[][] {
  const out: T[][] = []
  for (let i = 0; i < entries.length; i += max) out.push(entries.slice(i, i + max))
  return out
}

export interface SettleOutcome {
  marks: MarkRecord[]
  /** Entries refused because the comment changed on both sides: they leave the queue and wait for the student. */
  conflicts: Array<{ entry: EntryLike; detail: AnnotationConflictDetail }>
  /** Entries refused for good (invalid, over the cap, mark gone). */
  rejected: Array<{ entry: EntryLike; error: BatchError }>
  accepted: number
  /** Fields a newer write replaced (`overwritten`), for one quiet notice. */
  overwritten: string[]
  /** A delete lost to a newer edit on another device. */
  editWins: number
  /** The server brought a deleted mark back because this device edited it. */
  restored: number
  /** True when the local copy no longer matches the server and a refetch from 0 would settle it. */
  needsResync: boolean
}

/**
 * Applies the answers of a batch to the local copy. `entries` and `results` are in the same order. A mark that still has
 * later writes waiting keeps them on top of the server's version.
 */
export function settleResults(
  marks: readonly MarkRecord[],
  entries: readonly EntryLike[],
  results: readonly BatchResultItem[],
  stillWaiting: readonly EntryLike[],
  now: string,
): SettleOutcome {
  const byId = new Map(marks.map((m) => [m.id, m]))
  const waitingBy = groupByMark(stillWaiting)
  const out: SettleOutcome = {
    marks: [],
    conflicts: [],
    rejected: [],
    accepted: 0,
    overwritten: [],
    editWins: 0,
    restored: 0,
    needsResync: false,
  }
  entries.forEach((entry, i) => {
    const result = results[i]
    const id = entryMarkId(entry)
    if (!result) return
    if (result.status === 'ok') {
      out.accepted += 1
      out.overwritten.push(...(result.overwritten ?? []))
      if (result.edit_wins) out.editWins += 1
      if (result.restored) out.restored += 1
      const later = waitingBy.get(id)
      byId.set(id, later ? overlay({ ...result.annotation }, later, now) : { ...result.annotation })
    } else if (result.status === 'conflict') {
      out.conflicts.push({ entry, detail: result.error.details as AnnotationConflictDetail })
    } else {
      out.rejected.push({ entry, error: result.error })
      const body = bodyOf(entry)
      if (isCreateBody(body)) byId.delete(id)
      else out.needsResync = true
    }
  })
  out.marks = [...byId.values()]
  return out
}

/** The same rule for the single-request path: one answer for one entry. */
export function settleResponse(
  marks: readonly MarkRecord[],
  annotation: Annotation,
  stillWaiting: readonly EntryLike[],
  now: string,
): MarkRecord[] {
  const entry: EntryLike = { clientId: '', body: { op: 'upsert', id: annotation.id }, queuedAt: 0 }
  return settleResults(marks, [entry], [{ id: annotation.id, status: 'ok', annotation }], stillWaiting, now).marks
}

// ---- Conflicts ---------------------------------------------------------------------------------------------------------

/** The body that settles a parked comment conflict: based on the stored revision, with the student's choice. */
export function resolutionBody(parked: BatchOpBody, theirs: Annotation, resolution: Resolution): BatchOpBody {
  const { base: _base, ...rest } = parked
  return { ...rest, op: 'upsert', base_rev: theirs.rev, base: { comment: theirs.comment }, resolution }
}

export const marksNeedingResync = (outcome: Pick<SettleOutcome, 'needsResync'>) => outcome.needsResync

/** The count shown when no write has answered yet. */
export function localMarksInfo(live: number, lastKnown?: MarksInfo | null): MarksInfo {
  const limit = lastKnown?.limit ?? DEFAULT_MARKS_LIMIT
  return { count: live, limit, near_limit: live >= limit * 0.95 }
}
