import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'

import { currentUserId } from '~/lib/offline-queue'
import { errorsOf, type Issue, lint } from '~/lib/richtext'
import { useOnline } from '~/modules/personalization'

import { notesAnalytics } from '../lib/analytics'
import { getNote, patchNote } from '../lib/api'
import { createAutosave } from '../lib/autosave'
import { linkFields, linkFromSelection, type LinkSelection, selectionFromLink } from '../lib/chapter-link'
import { type BodyError, invalidBody, isNotFound, noteConflict, quotaExceeded } from '../lib/errors'
import { notesKeys } from '../lib/keys'
import { FALLBACK_LIMITS } from '../lib/limits'
import { notify } from '../lib/notify'
import { clearDraft, type Draft, draftKey, loadDraft, saveDraft } from '../lib/offline-store'
import { createNoteOrQueue, patchNoteOrQueue, queuedNoteWrites } from '../lib/queue'
import type { Note, NoteConflictDetail, NotePatch, Resolution } from '../lib/types'
import { applyEditLocally, storeNote } from './noteCache'
import { reportPatch } from './useNoteActions'
import { useNote, useUsage } from './useNotesQueries'

export interface EditorConflict {
  detail: NoteConflictDetail
  mine: { title: string; body: string }
}

export type SaveProblem = { kind: 'lint'; issues: Issue[] } | { kind: 'server'; errors: BodyError[] }

interface Options {
  /** The note to edit. A new note has its id from the start (made on this device, see `useStartNote`). */
  noteId: string
}

/**
 * The state behind the note editor: the text, the 2 second autosave, the local draft that is written first, recovery
 * of a draft after a crash, offline saves, auto merge notices and the conflict sheet. Everything the student types is
 * on this device before any request is made, so no failure here loses text.
 */
export function useNoteEditor({ noteId }: Options) {
  const qc = useQueryClient()
  const online = useOnline()
  const query = useNote(noteId)
  const usage = useUsage()
  const maxChars = usage.data?.limits.max_note_chars ?? FALLBACK_LIMITS.maxNoteChars

  const [title, setTitleState] = useState('')
  const [body, setBodyState] = useState('')
  const [selection, setSelectionState] = useState<LinkSelection | null>(null)
  const [ready, setReady] = useState(false)
  const [recovered, setRecovered] = useState(false)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [conflict, setConflict] = useState<EditorConflict | null>(null)
  const [serverProblems, setServerProblems] = useState<BodyError[]>([])
  const [saveFailed, setSaveFailed] = useState(false)
  const [resolving, setResolving] = useState(false)

  // Live values for the save function, which must always read the newest text without being rebuilt.
  const titleRef = useRef(title)
  const bodyRef = useRef(body)
  const selectionRef = useRef<LinkSelection | null>(null)
  const baseRev = useRef<number | null>(null)
  const baseBody = useRef<string | undefined>(undefined)
  const idRef = useRef<string>(noteId)
  const createdTracked = useRef(false)
  const conflictRef = useRef<EditorConflict | null>(null)
  const queuedBody = useRef<string | null>(null)
  const initialised = useRef(false)

  const note = query.data

  const persistDraft = useCallback(async () => {
    const userId = await currentUserId()
    if (!userId) return
    const draft: Draft = {
      userId,
      key: draftKey(idRef.current, ''),
      noteId: idRef.current,
      clientId: idRef.current,
      title: titleRef.current,
      body: bodyRef.current,
      baseRev: baseRev.current,
      baseBody: baseBody.current,
      selection: selectionRef.current,
      updatedAt: Date.now(),
    }
    await saveDraft(draft).catch(() => undefined)
  }, [])

  const dropDraft = useCallback(async () => {
    const userId = await currentUserId()
    if (userId) await clearDraft(userId, draftKey(idRef.current, '')).catch(() => undefined)
  }, [])

  // ---- Start: the note from the server (or this device), or the draft of an unsaved new note ----------------------
  useEffect(() => {
    if (initialised.current) return
    let alive = true
    void (async () => {
      const userId = await currentUserId()
      if (!note) return
      const draft = userId ? await loadDraft(userId, draftKey(noteId, '')) : undefined
      if (!alive) return
      const differs = draft && (draft.title !== note.title || draft.body !== note.body_md)
      const newer = draft && draft.updatedAt > new Date(note.updated_at).getTime() - 1000
      const useDraft = Boolean(differs && newer)
      const start =
        useDraft && draft ? { title: draft.title, body: draft.body } : { title: note.title, body: note.body_md }
      titleRef.current = start.title
      bodyRef.current = start.body
      selectionRef.current = selectionFromLink(note.link)
      baseRev.current = useDraft && typeof draft?.baseRev === 'number' ? draft.baseRev : note.rev
      baseBody.current = useDraft && draft?.baseBody !== undefined ? draft.baseBody : note.body_md
      setTitleState(start.title)
      setBodyState(start.body)
      setSelectionState(selectionRef.current)
      if (useDraft) {
        setRecovered(true)
        notify.recovered()
      }
      initialised.current = true
      setReady(true)
    })()
    return () => {
      alive = false
    }
  }, [noteId, note])

  // ---- Saving -------------------------------------------------------------------------------------------------------

  const adopt = useCallback((saved: Note, options: { merged?: boolean } = {}) => {
    baseRev.current = saved.rev
    baseBody.current = saved.body_md
    queuedBody.current = null
    if (options.merged || saved.body_md !== bodyRef.current) {
      // The server's text differs from what is on screen only after a merge or a resolution: show theirs.
      if (options.merged) notify.autoMerged()
      bodyRef.current = saved.body_md
      titleRef.current = saved.title
      setBodyState(saved.body_md)
      setTitleState(saved.title)
    }
    setSavedAt(Date.now())
    setSaveFailed(false)
    setServerProblems([])
  }, [])

  /** After text waited offline and was sent, the server's revision moved on: take it as the new base if nothing differs. */
  const refreshBase = useCallback(async () => {
    const id = idRef.current
    if (!id || queuedBody.current === null) return
    const waiting = (await queuedNoteWrites()).some((e) => e.path.includes(id))
    if (waiting) return
    try {
      const server = await getNote(id)
      if (server.body_md === queuedBody.current) {
        baseRev.current = server.rev
        baseBody.current = server.body_md
        queuedBody.current = null
      }
    } catch {
      // Still offline: the next save queues again.
    }
  }, [])

  const saveExisting = useCallback(
    async (id: string, source: 'autosave' | 'manual') => {
      await refreshBase()
      const t = titleRef.current
      const b = bodyRef.current
      const result = await patchNoteOrQueue(
        id,
        { base_rev: baseRev.current ?? 0, title: t, body_md: b, base_body_md: baseBody.current, source },
        t,
      )
      if (result.status === 'saved') {
        reportPatch(result.data)
        const typedSince = bodyRef.current !== b || titleRef.current !== t
        const merged = Boolean(result.data.merged)
        await storeNote(qc, result.data)
        if (typedSince && !merged) {
          baseRev.current = result.data.rev
          baseBody.current = result.data.body_md
          setSavedAt(Date.now())
        } else {
          adopt(result.data, { merged })
        }
        await dropDraftIfClean(b, t)
        notesAnalytics.noteSaved({ autosave: source === 'autosave', chars: b.length, offline: false })
      } else {
        queuedBody.current = b
        await applyEditLocally(qc, id, { title: t, body_md: b }, true)
        notesAnalytics.noteSaved({ autosave: source === 'autosave', chars: b.length, offline: true })
        notesAnalytics.writeQueued((await queuedNoteWrites()).length)
        void qc.invalidateQueries({ queryKey: notesKeys.queue })
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [qc, adopt, refreshBase],
  )

  const dropDraftIfClean = useCallback(
    async (savedBody: string, savedTitle: string) => {
      if (bodyRef.current === savedBody && titleRef.current === savedTitle) await dropDraft()
    },
    [dropDraft],
  )

  /** Notes born on this device have no server row until the create is confirmed: the save is the idempotent create. */
  const isLocalOnly = useCallback(
    () => (qc.getQueryData<Note>(notesKeys.note(idRef.current)) ?? note)?.local_only === true,
    [qc, note],
  )

  const trackCreated = useCallback(() => {
    if (createdTracked.current) return
    createdTracked.current = true
    notesAnalytics.noteCreated({
      source: selectionRef.current ? 'capture' : 'new',
      hasChapter: selectionRef.current !== null,
      first: usage.data?.used.notes === 0,
    })
  }, [usage.data?.used.notes])

  const saveLocalOnly = useCallback(
    async (id: string, source: 'autosave' | 'manual') => {
      const t = titleRef.current
      const b = bodyRef.current
      if (t.trim() === '' && b.trim() === '') return // an empty note is never sent
      const link = linkFields(selectionRef.current)
      const tags = qc.getQueryData<Note>(notesKeys.note(id))?.tags ?? []
      const result = await createNoteOrQueue(id, {
        title: t,
        body_md: b,
        ...link,
        ...(tags.length > 0 ? { tag_ids: tags.map((tag) => tag.id) } : {}),
      })
      if (result.status === 'queued') {
        // Waits in the queue (or was folded into the create already waiting there); the text stays on this device.
        queuedBody.current = b
        if (result.fresh) trackCreated()
        await applyEditLocally(qc, id, { title: t, body_md: b }, true)
        notesAnalytics.noteSaved({ autosave: source === 'autosave', chars: b.length, offline: true })
        notesAnalytics.writeQueued((await queuedNoteWrites()).length)
        void qc.invalidateQueries({ queryKey: notesKeys.queue })
        return
      }
      let created = result.data
      // A replay answers with the row stored first. Bring it up to the text on screen.
      if (created.body_md !== b || created.title !== t) {
        created = await patchNote(created.id, {
          base_rev: created.rev,
          base_body_md: created.body_md,
          title: t,
          body_md: b,
          source,
        })
      }
      baseRev.current = created.rev
      baseBody.current = created.body_md
      await storeNote(qc, created)
      await dropDraftIfClean(b, t)
      trackCreated()
      notesAnalytics.noteSaved({ autosave: source === 'autosave', chars: b.length, offline: false })
      void qc.invalidateQueries({ queryKey: notesKeys.lists })
      void qc.invalidateQueries({ queryKey: notesKeys.allCounts })
      setSavedAt(Date.now())
      setSaveFailed(false)
      setServerProblems([])
    },
    [qc, dropDraftIfClean, trackCreated],
  )

  const lintIssues = useDeferredValue(useMemo(() => errorsOf(lint(body, 'note')), [body]))
  const tooLong = body.length > maxChars
  const blocked = lintIssues.length > 0 || tooLong
  const blockedRef = useRef(blocked)
  blockedRef.current = blocked

  // The autosave closure is built once; it reaches the newest save functions through `latest`.
  const latest = useRef({ saveExisting, saveLocalOnly, isLocalOnly })
  latest.current = { saveExisting, saveLocalOnly, isLocalOnly }

  const [autosaveInstance] = useState(() =>
    createAutosave({
      save: async () => {
        setDirty(false)
        if (conflictRef.current || blockedRef.current) return
        setSaving(true)
        try {
          if (latest.current.isLocalOnly()) await latest.current.saveLocalOnly(idRef.current, 'autosave')
          else await latest.current.saveExisting(idRef.current, 'autosave')
        } catch (error) {
          const detail = noteConflict(error)
          if (detail) {
            const c = { detail, mine: { title: titleRef.current, body: bodyRef.current } }
            conflictRef.current = c
            setConflict(c)
            return
          }
          const problems = invalidBody(error)
          if (problems) {
            setServerProblems(problems)
            return
          }
          const quota = quotaExceeded(error)
          if (quota) {
            notesAnalytics.quotaBlocked(quota.kind)
            notify.quotaFull(quota.kind)
            setSaveFailed(true)
            return
          }
          if (isNotFound(error)) {
            setSaveFailed(true)
            return
          }
          setSaveFailed(true)
          throw error
        } finally {
          setSaving(false)
        }
      },
    }),
  )
  const autosave = useRef(autosaveInstance)

  const touch = useCallback(() => {
    void persistDraft()
    setDirty(true)
    autosave.current.touch()
  }, [persistDraft])

  const setTitle = useCallback(
    (value: string) => {
      titleRef.current = value
      setTitleState(value)
      setRecovered(false)
      touch()
    },
    [touch],
  )
  const setBody = useCallback(
    (value: string) => {
      bodyRef.current = value
      setBodyState(value)
      setRecovered(false)
      touch()
    },
    [touch],
  )

  /** Linking is a deliberate choice, so it saves at once (an existing note) or rides along with the first save. */
  const setSelection = useCallback(
    async (next: LinkSelection | null, via: 'manual' | 'suggestion' = 'manual') => {
      selectionRef.current = next
      setSelectionState(next)
      const id = idRef.current
      if (latest.current.isLocalOnly()) {
        // Not on the server yet: the filing is kept here and rides along with the create.
        await applyEditLocally(qc, id, { link: linkFromSelection(next) }, true)
        notesAnalytics.itemLinked(next ? via : 'manual')
        touch()
        return
      }
      const before = qc.getQueryData<Note>(notesKeys.note(id))
      const patch: NotePatch = {
        base_rev: baseRev.current ?? 0,
        ...linkFields(next),
        ...(before ? { base: { chapter_id: before.link.chapter_id, topic_id: before.link.topic_id } } : {}),
        source: 'manual',
      }
      try {
        const result = await patchNoteOrQueue(id, patch, titleRef.current)
        if (result.status === 'saved') {
          reportPatch(result.data)
          baseRev.current = result.data.rev
          await storeNote(qc, { ...result.data, link: linkFromSelection(next) })
          qc.setQueryData(notesKeys.note(id), result.data)
          notify.filed(next ? next.chapterName : 'Unfiled')
        } else {
          await applyEditLocally(qc, id, { link: linkFromSelection(next) }, true)
          notify.queued()
        }
        notesAnalytics.itemLinked(next ? via : 'manual')
        void qc.invalidateQueries({ queryKey: notesKeys.lists })
        void qc.invalidateQueries({ queryKey: notesKeys.allCounts })
        void qc.invalidateQueries({ queryKey: notesKeys.overviews })
      } catch (error) {
        notify.error(error, 'Could not file the note.')
      }
    },
    [qc, touch],
  )

  const saveNow = useCallback(async () => {
    if (blockedRef.current) return
    autosave.current.touch()
    await autosave.current.flush()
  }, [])

  // Leaving the page or hiding the tab saves at once; the draft is already on the device.
  useEffect(() => {
    const flush = () => void autosave.current.flush()
    const hide = () => document.visibilityState === 'hidden' && flush()
    document.addEventListener('visibilitychange', hide)
    window.addEventListener('pagehide', flush)
    const current = autosave.current
    return () => {
      document.removeEventListener('visibilitychange', hide)
      window.removeEventListener('pagehide', flush)
      void current.flush()
    }
  }, [])

  // Idle editor: follow the server (another device, a replayed queue, a version restore).
  useEffect(() => {
    if (!note || !initialised.current || note.local_only) return
    if (autosave.current.status() !== 'idle' || conflictRef.current) return
    if (baseRev.current !== null && note.rev > baseRev.current && queuedBody.current === null) {
      baseRev.current = note.rev
      baseBody.current = note.body_md
      if (note.body_md !== bodyRef.current || note.title !== titleRef.current) {
        bodyRef.current = note.body_md
        titleRef.current = note.title
        setBodyState(note.body_md)
        setTitleState(note.title)
      }
    }
  }, [note, noteId])

  const resolveConflict = useCallback(
    async (resolution: Resolution) => {
      const current = conflictRef.current
      const id = idRef.current
      if (!current || !id) return
      setResolving(true)
      try {
        const saved = await patchNote(id, {
          base_rev: current.detail.theirs.rev,
          title: current.mine.title,
          body_md: current.mine.body,
          base_body_md: current.detail.theirs.body_md,
          resolution,
          source: 'manual',
        })
        conflictRef.current = null
        setConflict(null)
        await storeNote(qc, saved)
        adopt(saved)
        await dropDraft()
        notesAnalytics.conflictResolved(resolution)
        notify.conflictResolved()
        void qc.invalidateQueries({ queryKey: notesKeys.lists })
      } catch (error) {
        notify.error(error, 'Could not settle the conflict. Try again.')
      } finally {
        setResolving(false)
      }
    },
    [qc, adopt, dropDraft],
  )

  const discardRecovered = useCallback(async () => {
    setRecovered(false)
    if (idRef.current && note) {
      titleRef.current = note.title
      bodyRef.current = note.body_md
      setTitleState(note.title)
      setBodyState(note.body_md)
      baseRev.current = note.rev
      baseBody.current = note.body_md
    } else {
      titleRef.current = ''
      bodyRef.current = ''
      setTitleState('')
      setBodyState('')
    }
    autosave.current.cancel()
    await dropDraft()
  }, [note, dropDraft])

  const problems: SaveProblem | null =
    lintIssues.length > 0
      ? { kind: 'lint', issues: lintIssues }
      : serverProblems.length > 0
        ? { kind: 'server', errors: serverProblems }
        : null

  const status = query.isPending
    ? 'loading'
    : query.isError && !note
      ? isNotFound(query.error)
        ? 'notfound'
        : 'error'
      : ready
        ? 'ready'
        : 'loading'

  return {
    status: status as 'loading' | 'ready' | 'error' | 'notfound',
    note,
    online,
    title,
    body,
    selection,
    setTitle,
    setBody,
    setSelection,
    saveNow,
    saving: saving || dirty,
    savedAt,
    saveFailed,
    recovered,
    discardRecovered,
    problems,
    tooLong,
    overBy: Math.max(0, body.length - maxChars),
    maxChars,
    conflict,
    resolving,
    resolveConflict,
    refetch: query.refetch,
    /** The note exists only on this device: the server has not confirmed its row yet. */
    localOnly: note?.local_only === true,
  }
}
