import {
  currentUserId,
  enqueue,
  flushQueue,
  type FlushResult,
  parkConflict,
  parkedConflicts,
  pending,
  pendingScopes,
  type QueuedWrite,
  queueStamp,
  removeEntry,
  resolveParked,
} from '~/lib/offline-queue'

import {
  annotationScope,
  batchesOf,
  bodyOf,
  type EntryLike,
  entryMarkId,
  type LocalOp,
  planWrite,
  resolutionBody,
} from './annotation-sync'
import type {
  AnnotationConflictDetail,
  BatchError,
  BatchOpBody,
  BatchResponse,
  BatchResultItem,
  MarksInfo,
  Resolution,
  WriteResponse,
} from './annotation-types'
import { batchMarks, MAX_BATCH, putMark, requestOf } from './annotations-api'

/**
 * The IO around the pure planner: the marks of a document are written to the shared persisted queue, one lane per
 * document (`notes-ann:<documentId>`), replayed in batches of at most 100 and parked when a comment conflicts. The
 * queue itself (IndexedDB, in-order replay, one flusher per account through Web Locks, retry) is `~/lib/offline-queue`.
 */

const labelOf = (body: BatchOpBody) => (typeof body.kind === 'string' ? body.kind : undefined)
const clientIdFor = (markId: string) => `ann:${markId}:${crypto.randomUUID().slice(0, 8)}`

/** Writes in a request that is out right now: a newer edit must never fold into one (it would be deleted when the answer arrives). */
const inFlight = new Set<string>()

/** Test hook. */
export const resetAnnotationQueue = () => inFlight.clear()

function entryFor(userId: string, documentId: string, body: BatchOpBody, base?: QueuedWrite): QueuedWrite {
  const request = requestOf(body)
  return {
    clientId: base?.clientId ?? clientIdFor(body.id),
    userId,
    scope: annotationScope(documentId),
    method: request.method,
    path: request.path,
    body,
    queuedAt: base?.queuedAt ?? queueStamp(),
    label: labelOf(body) ?? base?.label,
  }
}

export interface QueueResult {
  plan: 'enqueue' | 'replace' | 'cancel'
  /** The entries now waiting for this document, so the screen can show the count without another read. */
  waiting: number
}

/** Plans one local action against what already waits for the same mark and stores the outcome. Resolves when it is durable. */
export async function queueMarkWrite(documentId: string, markId: string, op: LocalOp): Promise<QueueResult | null> {
  const userId = await currentUserId()
  if (!userId) return null
  const scope = annotationScope(documentId)
  const rows = await pending(userId, scope)
  const mine = rows.filter((e) => entryMarkId(e) === markId)
  const last = mine[mine.length - 1]
  const foldable: EntryLike[] = last && inFlight.has(last.clientId) ? [] : mine
  const plan = planWrite(foldable, op)
  if (plan.action === 'cancel') {
    for (const id of plan.clientIds) await removeEntry(id)
    return { plan: 'cancel', waiting: rows.length - plan.clientIds.length }
  }
  if (plan.action === 'replace') {
    const existing = rows.find((e) => e.clientId === plan.clientId)
    await enqueue(entryFor(userId, documentId, plan.body, existing))
    return { plan: 'replace', waiting: rows.length }
  }
  await enqueue(entryFor(userId, documentId, plan.body))
  return { plan: 'enqueue', waiting: rows.length + 1 }
}

export async function waitingWrites(documentId: string): Promise<QueuedWrite[]> {
  const userId = await currentUserId()
  return userId ? pending(userId, annotationScope(documentId)) : []
}

/** Every document of this account that still has writes waiting (to flush them all when the browser is back online). */
export async function documentsWithWaitingWrites(): Promise<string[]> {
  const userId = await currentUserId()
  if (!userId) return []
  return (await pendingScopes(userId, 'notes-ann:')).map((scope) => scope.slice('notes-ann:'.length))
}

// ---- Flushing ----------------------------------------------------------------------------------------------------------

export interface SettleReport {
  conflicts: Array<{ entry: EntryLike; detail: AnnotationConflictDetail }>
  rejected: Array<{ entry: EntryLike; error: BatchError }>
}

export interface FlushHooks {
  /**
   * The batch answered: apply it to the screen's copy and say which entries were refused. `stillWaiting` are the entries
   * queued behind the batch, which stay on top of the server's versions.
   */
  settle: (batch: {
    entries: QueuedWrite[]
    results: BatchResultItem[]
    stillWaiting: QueuedWrite[]
    response: BatchResponse
  }) => SettleReport
  onParked?: (entry: QueuedWrite, detail: AnnotationConflictDetail) => void
  onDropped?: (entry: QueuedWrite, error: BatchError) => void
  /** Told for every batch that went through: how many writes it carried and the oldest one's age (analytics, counters). */
  onSent?: (count: number, oldestQueuedAt: number | undefined, marks: MarksInfo | undefined) => void
}

const MAX_ROUNDS = 5

/**
 * Replays one document's lane: consecutive entries go in one request (at most 100, in order). A conflicting op is
 * parked on its own, a refused op is dropped on its own, and neither blocks the ones behind it. A network or server
 * error stops the run with the order kept (the queue retries it).
 */
export async function flushMarks(documentId: string, hooks: FlushHooks): Promise<FlushResult | null> {
  const scope = annotationScope(documentId)
  let total: FlushResult | null = null
  for (let round = 0; round < MAX_ROUNDS; round++) {
    const handled = new Set<string>()
    const result = await flushQueue({
      scope,
      send: async (entry) => {
        if (handled.has(entry.clientId)) return undefined
        const rows = await pending(entry.userId, scope)
        const start = Math.max(
          0,
          rows.findIndex((e) => e.clientId === entry.clientId),
        )
        const [group] = batchesOf(rows.slice(start), MAX_BATCH) as [QueuedWrite[]]
        for (const e of group) inFlight.add(e.clientId)
        try {
          const response = await batchMarks(documentId, group.map(bodyOf))
          for (const e of group) handled.add(e.clientId)
          const stillWaiting = rows.slice(start + group.length)
          const report = hooks.settle({ entries: group, results: response.results, stillWaiting, response })
          for (const { entry: parked, detail } of report.conflicts) {
            const original = group.find((e) => e.clientId === parked.clientId) as QueuedWrite
            await parkConflict({
              clientId: original.clientId,
              userId: original.userId,
              scope,
              entry: original,
              detail: { markId: entryMarkId(original), documentId, detail },
              parkedAt: Date.now(),
            })
            hooks.onParked?.(original, detail)
          }
          for (const { entry: refused, error } of report.rejected)
            hooks.onDropped?.(group.find((e) => e.clientId === refused.clientId) as QueuedWrite, error)
          hooks.onSent?.(group.length, group[0]?.queuedAt, response.marks)
          return response
        } finally {
          for (const e of group) inFlight.delete(e.clientId)
        }
      },
    })
    if (!result) return total
    total = total ? { ...result, sent: total.sent + result.sent, dropped: total.dropped + result.dropped } : result
    // Something was queued while the run was out: go again, but never past a stop (offline, server error, another tab).
    const more = result.busy || result.remaining > 0 ? 0 : (await waitingWrites(documentId)).length
    if (more === 0) return total
  }
  return total
}

// ---- Parked conflicts --------------------------------------------------------------------------------------------------

export interface ParkedMark {
  clientId: string
  markId: string
  documentId: string
  detail: AnnotationConflictDetail
  entry: QueuedWrite
  parkedAt: number
}

export async function parkedMarkConflicts(documentId: string): Promise<ParkedMark[]> {
  const userId = await currentUserId()
  if (!userId) return []
  return (await parkedConflicts(userId, annotationScope(documentId))).map((p) => {
    const info = p.detail as { markId: string; documentId: string; detail: AnnotationConflictDetail }
    return {
      clientId: p.clientId,
      markId: info.markId,
      documentId: info.documentId,
      detail: info.detail,
      entry: p.entry,
      parkedAt: p.parkedAt,
    }
  })
}

/** Sends the student's choice for a parked comment, based on the stored revision, and forgets the parked entry. */
export async function resolveMarkConflict(parked: ParkedMark, resolution: Resolution): Promise<WriteResponse> {
  const body = resolutionBody(bodyOf(parked.entry), parked.detail.theirs, resolution)
  const response = await putMark(body)
  await resolveParked(parked.clientId)
  return response
}
