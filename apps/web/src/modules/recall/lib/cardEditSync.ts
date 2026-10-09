import { type PatchCardBody, recallApi } from './api'
import { mergeFields } from './cardConflict'
import { cardEditQueue, type QueuedEdit } from './cardEditQueue'
import { cardFailure } from './cardErrors'

export interface EditSyncResult {
  sent: number
  needsAttention: number
  /** The connection failed or the server asked us to slow down: what is left stays queued and is tried again later. */
  stopped: boolean
}

type Patch = (cardId: string, body: PatchCardBody) => Promise<unknown>

const body = (e: QueuedEdit, rev: number, fields = e.fields): PatchCardBody => ({
  base_rev: rev,
  fields,
  importance: e.importance,
  tags: e.tags,
})

/**
 * Sends the edits written offline, one card at a time. A conflict where the two sides changed different parts is merged
 * and sent on top of the server's revision without asking; one where both changed the same part, a card deleted
 * meanwhile, or text the server refuses is marked for the student. Nothing is ever dropped silently.
 */
export async function flushEdits(userId: string, patch: Patch = recallApi.patchCard): Promise<EditSyncResult> {
  const result: EditSyncResult = { sent: 0, needsAttention: 0, stopped: false }
  for (const edit of cardEditQueue.list(userId).filter((e) => e.attention === null)) {
    let rev = edit.baseRev
    let fields = edit.fields
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        await patch(edit.cardId, body(edit, rev, fields))
        cardEditQueue.remove(userId, edit.cardId)
        result.sent += 1
        break
      } catch (error) {
        const f = cardFailure(error)
        if (f.kind === 'network' || f.kind === 'throttled') {
          result.stopped = true
          return result
        }
        if (f.kind === 'conflict' && f.rev !== null) {
          const theirs = { ...edit.fields, ...f.serverFields }
          const merge = mergeFields(edit.base, edit.fields, theirs)
          if (merge.conflicts.length === 0 && attempt === 0) {
            rev = f.rev
            fields = merge.merged
            continue
          }
          cardEditQueue.flag(userId, edit.cardId, { kind: 'conflict', theirs, rev: f.rev })
        } else if (f.kind === 'deleted') {
          cardEditQueue.flag(userId, edit.cardId, { kind: 'deleted' })
        } else {
          const message =
            f.kind === 'invalid'
              ? (f.issues[0]?.message ?? 'The server would not take this edit.')
              : 'The server would not take this edit.'
          cardEditQueue.flag(userId, edit.cardId, { kind: 'invalid', message })
        }
        result.needsAttention += 1
        break
      }
    }
  }
  return result
}
