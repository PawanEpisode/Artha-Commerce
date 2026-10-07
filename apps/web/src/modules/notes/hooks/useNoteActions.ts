import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { currentUserId } from '~/lib/offline-queue'

import { notesAnalytics } from '../lib/analytics'
import { createTag, restoreVersion } from '../lib/api'
import { linkFields, linkFromSelection, type LinkSelection } from '../lib/chapter-link'
import { quotaExceeded } from '../lib/errors'
import { notesKeys } from '../lib/keys'
import { notify } from '../lib/notify'
import { removeCachedNote } from '../lib/offline-store'
import type { LocalEdit } from '../lib/optimistic'
import {
  clipOrQueue,
  createNoteOrQueue,
  deleteNoteOrQueue,
  patchNoteOrQueue,
  restoreNoteOrQueue,
  type WriteOutcome,
} from '../lib/queue'
import type { Note, NotePatch, PatchResult, TagRef } from '../lib/types'
import { applyEditLocally, storeNote } from './noteCache'

type NoteRef = Pick<Note, 'id' | 'rev' | 'title' | 'created_at'> & Partial<Pick<Note, 'pinned' | 'link'>>

/** What the server said about a saved edit besides the new note: it brought the note back, or replaced another device's value. */
export function reportPatch(result: PatchResult) {
  if (result.restored) notify.restoredByEdit()
  if (result.overwritten && result.overwritten.length > 0) notify.overwritten(result.overwritten)
}

export interface MetaChange {
  pinned?: boolean
  /** `null` files the note under "Unfiled". */
  selection?: LinkSelection | null
  /** The whole tag set; `tags` carries the rows to show before the server answers. */
  tagIds?: string[]
  tags?: TagRef[]
}

/**
 * Every write a notes list or card can make, in one place: each one shows its result at once, goes to the offline
 * queue when the network is gone, and refreshes the lists, counts and overviews it touches.
 */
export function useNoteActions() {
  const qc = useQueryClient()

  const refresh = useCallback(
    () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: notesKeys.lists }),
        qc.invalidateQueries({ queryKey: notesKeys.aggregates }),
        qc.invalidateQueries({ queryKey: notesKeys.allCounts }),
        qc.invalidateQueries({ queryKey: notesKeys.overviews }),
        qc.invalidateQueries({ queryKey: notesKeys.usage }),
        qc.invalidateQueries({ queryKey: notesKeys.tags }),
      ]),
    [qc],
  )

  /** Quota errors become one toast; everything else is the caller's to word. Returns true when it handled the error. */
  const handleQuota = useCallback((error: unknown) => {
    const quota = quotaExceeded(error)
    if (!quota) return false
    notesAnalytics.quotaBlocked(quota.kind)
    notify.quotaFull(quota.kind)
    return true
  }, [])

  const restore = useCallback(
    async (note: Pick<Note, 'id' | 'created_at'>) => {
      try {
        const result = await restoreNoteOrQueue(note.id)
        if (result.status === 'saved') await storeNote(qc, result.data)
        notesAnalytics.noteRestored(note.created_at)
        notify.restored()
        await refresh()
        return true
      } catch (error) {
        if (!handleQuota(error)) notify.error(error, 'Could not restore the note.')
        return false
      }
    },
    [qc, refresh, handleQuota],
  )

  const trash = useCallback(
    async (note: NoteRef) => {
      try {
        const result = await deleteNoteOrQueue(note.id)
        const userId = await currentUserId()
        if (userId) await removeCachedNote(userId, note.id)
        qc.removeQueries({ queryKey: notesKeys.note(note.id) })
        if (result.status === 'queued') notify.queued()
        notesAnalytics.noteDeleted(note.created_at)
        notify.trashed(() => void restore(note))
        await refresh()
        return true
      } catch (error) {
        notify.error(error, 'Could not move the note to Trash.')
        return false
      }
    },
    [qc, refresh, restore],
  )

  const change = useCallback(
    async (note: NoteRef, meta: MetaChange): Promise<Note | undefined> => {
      const patch: NotePatch = { base_rev: note.rev, source: 'manual' }
      const edit: LocalEdit = {}
      const base: NonNullable<NotePatch['base']> = {}
      if (meta.pinned !== undefined) {
        patch.pinned = meta.pinned
        if (note.pinned !== undefined) base.pinned = note.pinned
        edit.pinned = meta.pinned
      }
      if (meta.selection !== undefined) {
        Object.assign(patch, linkFields(meta.selection))
        if (note.link) {
          base.chapter_id = note.link.chapter_id
          base.topic_id = note.link.topic_id
        }
        edit.link = linkFromSelection(meta.selection)
      }
      if (meta.tagIds !== undefined) {
        patch.tag_ids = meta.tagIds
        if (meta.tags) edit.tags = meta.tags
      }
      if (Object.keys(base).length > 0) patch.base = base
      try {
        const result: WriteOutcome<PatchResult> = await patchNoteOrQueue(note.id, patch, note.title)
        const saved =
          result.status === 'saved'
            ? (await storeNote(qc, result.data), result.data)
            : await applyEditLocally(qc, note.id, edit, true)
        if (result.status === 'queued') notify.queued()
        else reportPatch(result.data)
        await refresh()
        return saved
      } catch (error) {
        notify.error(error, 'Could not save that change.')
        return undefined
      }
    },
    [qc, refresh],
  )

  const pin = useCallback(
    async (note: NoteRef, pinned: boolean) => {
      const done = await change(note, { pinned })
      if (done) notify.pinned(pinned)
      return done
    },
    [change],
  )

  const create = useCallback(
    async (input: Parameters<typeof createNoteOrQueue>[0]) => {
      const result = await createNoteOrQueue(input)
      if (result.status === 'saved') await storeNote(qc, result.data)
      await refresh()
      return result
    },
    [qc, refresh],
  )

  const clip = useCallback(
    async (input: Parameters<typeof clipOrQueue>[0]) => {
      const result = await clipOrQueue(input)
      await refresh()
      return result
    },
    [refresh],
  )

  const restoreOldVersion = useCallback(
    async (noteId: string, rev: number, createdAt: string) => {
      try {
        const note = await restoreVersion(noteId, rev)
        await storeNote(qc, note)
        await qc.invalidateQueries({ queryKey: notesKeys.versions(noteId) })
        notesAnalytics.versionRestored(createdAt)
        notify.versionRestored(rev)
        await refresh()
        return note
      } catch (error) {
        notify.error(error, 'Could not restore that version.')
        return undefined
      }
    },
    [qc, refresh],
  )

  const addTag = useCallback(
    async (name: string) => {
      try {
        const tag = await createTag({ name })
        await qc.invalidateQueries({ queryKey: notesKeys.tags })
        return tag
      } catch (error) {
        if (!handleQuota(error)) notify.error(error, 'Could not create the tag.')
        return undefined
      }
    },
    [qc, handleQuota],
  )

  return { create, clip, trash, restore, pin, change, restoreOldVersion, addTag, refresh, handleQuota }
}
