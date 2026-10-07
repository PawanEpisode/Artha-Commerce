import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { currentUserId } from '~/lib/offline-queue'
import { useOnline } from '~/modules/personalization'

import { type AddTool, annotationAnalytics } from '../lib/annotation-analytics'
import { type MarksNotice, marksNotice } from '../lib/annotation-limits'
import { markNotify } from '../lib/annotation-notify'
import {
  documentsWithWaitingWrites,
  flushMarks,
  type ParkedMark,
  parkedMarkConflicts,
  queueMarkWrite,
  waitingWrites,
} from '../lib/annotation-queue'
import { deviceId, readCachedMarks, writeCachedMarks } from '../lib/annotation-store'
import {
  applyBody,
  applyPending,
  createBody,
  editBody,
  type EntryLike,
  liveMarks,
  localMarksInfo,
  mergeDelta,
  needsFullResync,
  newMarkRecord,
  pruneTombstones,
  replaceWithSnapshot,
  settleResponse,
  settleResults,
  sortMarks,
} from '../lib/annotation-sync'
import type { Annotation, MarkDraft, MarkFields, MarkPatch, MarkRecord, MarksInfo } from '../lib/annotation-types'
import type { CardKind } from '../lib/annotation-types'
import { getDelta, isNoText, isRecallUnavailable, makeCard as requestCard } from '../lib/annotations-api'
import type { DocumentDetail } from '../lib/document-types'
import { documentQuotaExceeded } from '../lib/errors'
import { linkForPage } from '../lib/mark-link'
import { deriveMarksSync } from '../lib/marks-sync-state'
import type { NoteLink, TagRef } from '../lib/types'

export const FOREGROUND_SYNC_MS = 30_000
const PERSIST_MS = 250
/** A replay worth reporting: the writes waited longer than an ordinary instant flush. */
const REPLAY_REPORT_MS = 5_000

export type MarksStatus = 'loading' | 'ready' | 'error'

export interface AddOptions {
  tool?: AddTool
  /** Tag chips to show at once (the ids are what is sent). */
  tags?: TagRef[]
  tagIds?: string[]
  chapterId?: string | null
  topicId?: string | null
  link?: NoteLink
}

export interface EditOptions {
  /** What the chapter chip shows until the server answers (the picker knows the names). */
  link?: NoteLink
  tags?: TagRef[]
}

export interface MarksController {
  /** Live marks in reading order. */
  marks: MarkRecord[]
  /** Everything held, tombstones included (the heaviest-pages and undo logic read it). */
  all: MarkRecord[]
  find: (id: string) => MarkRecord | undefined
  status: MarksStatus
  online: boolean
  sync: ReturnType<typeof deriveMarksSync>
  queued: number
  parked: ParkedMark[]
  info: MarksInfo
  notice: MarksNotice
  /** Saves a mark on this device at once and sends it in the background. Null when the PDF is at its cap. */
  add: (draft: MarkDraft, options?: AddOptions) => MarkRecord | null
  edit: (id: string, patch: MarkPatch, options?: EditOptions) => void
  /** Deletes with an Undo toast (10 s). */
  remove: (id: string, options?: { silent?: boolean }) => void
  restore: (id: string) => void
  makeCard: (id: string, kind?: CardKind) => Promise<boolean>
  /** Replays what waits, then pulls what changed elsewhere. */
  syncNow: () => Promise<void>
  /** For the conflict hook. */
  applyServerMark: (annotation: Annotation) => void
  refreshQueue: () => Promise<void>
}

/**
 * Whether the browser says it has a connection, read at the moment of use. The `online` event reaches these handlers
 * before React has re-rendered, so a value kept from the last render would still say "offline" when the connection returns.
 */
const reachable = () => typeof navigator === 'undefined' || navigator.onLine !== false

const SEEN_KEYS = ['page', 'color', 'comment'] as const

/** The values of a mark that an edit's `base` records (what the student last saw). */
function seenOf(mark: MarkRecord): Partial<MarkFields> {
  const seen: Partial<MarkFields> = {}
  for (const key of SEEN_KEYS) (seen as Record<string, unknown>)[key] = mark[key]
  seen.chapter_id = mark.chapter_source === 'explicit' ? mark.link.chapter_id : null
  seen.topic_id = mark.chapter_source === 'explicit' ? mark.link.topic_id : null
  return seen
}

/**
 * The marks of one document, local first (ERD decision 9, PRD 5.3): a mark is drawn and saved on this device in the same
 * tick, queued with its client id, and sent in the background in batches. The cache shows at once; the delta feed brings
 * what changed elsewhere on open, on reconnect, every 30 seconds while the tab is in front and when it comes back.
 */
export function useAnnotations(doc: Pick<DocumentDetail, 'id' | 'ranges' | 'link'>, enabled = true): MarksController {
  const documentId = doc.id
  const online = useOnline()
  const [marks, setMarks] = useState<MarkRecord[]>([])
  const [status, setStatus] = useState<MarksStatus>('loading')
  const [queued, setQueued] = useState(0)
  const [parked, setParked] = useState<ParkedMark[]>([])
  const [flushing, setFlushing] = useState(false)
  const [serverInfo, setServerInfo] = useState<MarksInfo | null>(null)

  const ref = useRef<MarkRecord[]>([])
  const sinceSeq = useRef(0)
  const syncedAt = useRef<number | null>(null)
  const infoRef = useRef<MarksInfo | null>(null)
  const docRef = useRef(doc)
  docRef.current = doc
  const alive = useRef(true)
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasCache = useRef(false)
  const delta = useRef<Promise<void> | null>(null)

  const nowIso = () => new Date().toISOString()

  // ---- Local copy -------------------------------------------------------------------------------------------------
  const persist = useCallback(async () => {
    const userId = await currentUserId()
    if (!userId) return
    await writeCachedMarks({
      userId,
      documentId,
      marks: pruneTombstones(ref.current, Date.now()),
      sinceSeq: sinceSeq.current,
      syncedAt: syncedAt.current,
      openedAt: Date.now(),
      marksInfo: infoRef.current,
    }).catch(() => undefined)
  }, [documentId])
  const persistSoon = useCallback(() => {
    if (persistTimer.current) clearTimeout(persistTimer.current)
    persistTimer.current = setTimeout(() => void persist(), PERSIST_MS)
  }, [persist])

  const commit = useCallback(
    (next: MarkRecord[]) => {
      ref.current = next
      if (alive.current) setMarks(next)
      persistSoon()
    },
    [persistSoon],
  )

  const refreshQueue = useCallback(async () => {
    const [waiting, conflicts] = await Promise.all([waitingWrites(documentId), parkedMarkConflicts(documentId)])
    if (!alive.current) return
    setQueued(waiting.length)
    setParked(conflicts)
  }, [documentId])

  // ---- Sending ----------------------------------------------------------------------------------------------------
  const pullDelta = useCallback(async () => {
    if (!reachable()) return
    if (delta.current) return delta.current
    delta.current = (async () => {
      const full = needsFullResync(syncedAt.current, Date.now())
      let since = full ? 0 : sinceSeq.current
      const items: Annotation[] = []
      for (let guard = 0; guard < 200; guard++) {
        const page = await getDelta(documentId, since)
        items.push(...page.items)
        since = page.next_since_seq
        if (!page.has_more) break
      }
      const waiting = await waitingWrites(documentId)
      const now = nowIso()
      commit(
        pruneTombstones(
          full ? replaceWithSnapshot(items, waiting, now) : mergeDelta(ref.current, items, waiting, now),
          Date.now(),
        ),
      )
      sinceSeq.current = since
      syncedAt.current = Date.now()
      hasCache.current = true
      if (alive.current) setStatus('ready')
    })()
      .catch(() => {
        if (alive.current && !hasCache.current && ref.current.length === 0) setStatus('error')
      })
      .finally(() => {
        delta.current = null
      })
    return delta.current
  }, [documentId, commit])

  const flush = useCallback(async () => {
    if (!reachable()) return
    setFlushing(true)
    let refused: Array<{ code: string; creates: boolean }> = []
    let needsResync = false
    try {
      await flushMarks(documentId, {
        settle: ({ entries, results, stillWaiting, response }) => {
          const outcome = settleResults(ref.current, entries, results, stillWaiting, nowIso())
          commit(outcome.marks)
          if (response.marks) {
            infoRef.current = response.marks
            setServerInfo(response.marks)
          }
          if (outcome.overwritten.length > 0) markNotify.overwritten([...new Set(outcome.overwritten)])
          if (outcome.editWins > 0) markNotify.editWins()
          refused = outcome.rejected.map((r) => ({ code: r.error.code, creates: !!(r.entry as EntryLike).body.kind }))
          needsResync ||= outcome.needsResync
          results.forEach((r, i) => {
            const entry = entries[i]
            const body = entry?.body as { op?: string; base_rev?: number } | undefined
            if (r.status !== 'ok' || body?.op !== 'upsert' || body.base_rev) return
            if (r.annotation.chapter_source === 'range') annotationAnalytics.linked('range')
            else if (r.annotation.chapter_source === 'document') annotationAnalytics.linked('document_default')
          })
          return { conflicts: outcome.conflicts, rejected: outcome.rejected }
        },
        onSent: (count, oldest) => {
          if (oldest && Date.now() - oldest > REPLAY_REPORT_MS) annotationAnalytics.queueReplayed(count, oldest)
        },
      })
    } catch {
      // A network or server error leaves the writes queued; the next trigger tries again.
    } finally {
      if (alive.current) setFlushing(false)
    }
    if (refused.length > 0) {
      if (refused.some((r) => r.code === 'quota_exceeded')) markNotify.limitReached()
      else markNotify.dropped(refused.length)
    }
    await refreshQueue()
    if (needsResync) {
      syncedAt.current = null
      await pullDelta()
    }
  }, [documentId, commit, refreshQueue, pullDelta])

  const syncNow = useCallback(async () => {
    await flush()
    await pullDelta()
  }, [flush, pullDelta])
  const syncRef = useRef(syncNow)
  syncRef.current = syncNow

  // ---- Open: cache first, then queue, then the feed -----------------------------------------------------------------
  useEffect(() => {
    if (!enabled) return
    alive.current = true
    let cancelled = false
    void (async () => {
      const userId = await currentUserId()
      const cached = userId ? await readCachedMarks(userId, documentId).catch(() => undefined) : undefined
      const waiting = await waitingWrites(documentId)
      if (cancelled) return
      // The queue is the truth for what has not reached the server: rebuild the local view from the cache plus the queue.
      commit(applyPending(cached?.marks ?? [], waiting, nowIso()))
      sinceSeq.current = cached?.sinceSeq ?? 0
      syncedAt.current = cached?.syncedAt ?? null
      infoRef.current = cached?.marksInfo ?? null
      setServerInfo(cached?.marksInfo ?? null)
      hasCache.current = !!cached
      // Offline with nothing cached there is nothing to wait for: the screen is ready, empty, and the chip says offline.
      if (cached || waiting.length > 0 || !reachable()) setStatus('ready')
      await refreshQueue()
      await syncRef.current()
    })()
    return () => {
      cancelled = true
      alive.current = false
      if (persistTimer.current) clearTimeout(persistTimer.current)
      void persist()
    }
  }, [documentId, enabled, commit, persist, refreshQueue])

  // ---- Triggers: reconnect, every 30 s in front, coming back to the tab ----------------------------------------------
  useEffect(() => {
    if (!enabled) return
    const onOnline = () => void syncRef.current()
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void syncRef.current()
      else void persist()
    }
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible' && reachable()) void syncRef.current()
    }, FOREGROUND_SYNC_MS)
    window.addEventListener('online', onOnline)
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', onVisibility)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('online', onOnline)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', onVisibility)
    }
  }, [enabled, persist])

  // Other documents of this account that still have writes waiting go out when this screen opens (one lane each).
  useEffect(() => {
    if (!enabled || !online) return
    void documentsWithWaitingWrites().then((ids) =>
      ids
        .filter((id) => id !== documentId)
        .forEach(
          (id) => void flushMarks(id, { settle: () => ({ conflicts: [], rejected: [] }) }).catch(() => undefined),
        ),
    )
  }, [enabled, online, documentId])

  // ---- Actions ------------------------------------------------------------------------------------------------------
  const queueThenSend = useCallback(
    (markId: string, op: Parameters<typeof queueMarkWrite>[2]) => {
      if (typeof navigator !== 'undefined' && navigator.onLine === false) annotationAnalytics.writeQueued(1)
      void queueMarkWrite(documentId, markId, op)
        .then(() => refreshQueue())
        .then(() => (reachable() ? flush() : undefined))
        .catch(() => undefined)
    },
    [documentId, flush, refreshQueue],
  )

  const liveCount = () => liveMarks(ref.current).length
  const limit = () => infoRef.current?.limit ?? localMarksInfo(0).limit

  const add = useCallback(
    (draft: MarkDraft, options: AddOptions = {}): MarkRecord | null => {
      if (liveCount() >= limit()) {
        markNotify.limitReached()
        return null
      }
      const id = crypto.randomUUID()
      const local = options.link
        ? { link: options.link, source: 'explicit' as const }
        : linkForPage(draft.page, docRef.current.ranges, docRef.current.link)
      const record = {
        ...newMarkRecord(draft, {
          id,
          documentId,
          deviceId: deviceId(),
          now: nowIso(),
          link: local.link,
          tags: options.tags,
        }),
        chapter_source: options.chapterId ? ('explicit' as const) : local.source,
      }
      commit([...ref.current, record])
      annotationAnalytics.added({
        kind: draft.kind,
        color: draft.color ?? null,
        hasChapter: !!local.link.chapter_id,
        tool: options.tool ?? 'tap',
      })
      queueThenSend(id, {
        type: 'create',
        body: createBody(record, { chapter_id: options.chapterId, topic_id: options.topicId, tag_ids: options.tagIds }),
      })
      return record
    },
    [documentId, commit, queueThenSend],
  )

  const edit = useCallback(
    (id: string, patch: MarkPatch, options: EditOptions = {}) => {
      const mark = ref.current.find((m) => m.id === id)
      if (!mark) return
      const body = editBody({ id, document_id: documentId, rev: Math.max(1, mark.rev) }, patch, seenOf(mark))
      const applied = applyBody(mark, body, nowIso()) as MarkRecord
      const next: MarkRecord = {
        ...applied,
        ...(options.link
          ? { link: options.link, chapter_source: options.link.chapter_id ? ('explicit' as const) : ('none' as const) }
          : {}),
        ...(options.tags ? { tags: options.tags } : {}),
      }
      if ('chapter_id' in patch && !options.link) {
        // Cleared: the mark re-inherits from its page's range or the document; the server tells which.
        const inherited = patch.chapter_id ? null : linkForPage(next.page, docRef.current.ranges, docRef.current.link)
        if (inherited) {
          next.link = inherited.link
          next.chapter_source = inherited.source
        }
      }
      commit(ref.current.map((m) => (m.id === id ? next : m)))
      annotationAnalytics.edited(mark.kind)
      if (patch.chapter_id) annotationAnalytics.linked('manual')
      queueThenSend(id, { type: 'edit', body })
    },
    [documentId, commit, queueThenSend],
  )

  const restore = useCallback(
    (id: string) => {
      const mark = ref.current.find((m) => m.id === id)
      if (!mark) return
      commit(ref.current.map((m) => (m.id === id ? { ...m, deleted_at: null, updated_at: nowIso() } : m)))
      annotationAnalytics.undone(mark.kind)
      queueThenSend(id, { type: 'restore', id, recreate: mark.local_only ? createBody(mark) : undefined })
    },
    [commit, queueThenSend],
  )

  const remove = useCallback(
    (id: string, options: { silent?: boolean } = {}) => {
      const mark = ref.current.find((m) => m.id === id)
      if (!mark || mark.deleted_at) return
      commit(ref.current.map((m) => (m.id === id ? { ...m, deleted_at: nowIso(), updated_at: nowIso() } : m)))
      annotationAnalytics.deleted(mark.kind)
      queueThenSend(id, { type: 'delete', id, baseRev: mark.rev })
      if (!options.silent) markNotify.deleted(mark.kind, () => restore(id))
    },
    [commit, queueThenSend, restore],
  )

  const applyServerMark = useCallback(
    (annotation: Annotation) => {
      void waitingWrites(documentId).then((waiting) =>
        commit(settleResponse(ref.current, annotation, waiting, nowIso())),
      )
    },
    [documentId, commit],
  )

  const makeCard = useCallback(
    async (id: string, kind?: CardKind): Promise<boolean> => {
      if (!reachable()) {
        markNotify.cardNeedsConnection()
        return false
      }
      await flush()
      const mark = ref.current.find((m) => m.id === id)
      if (!mark) return false
      try {
        const result = await requestCard(id, crypto.randomUUID(), kind)
        commit(ref.current.map((m) => (m.id === id ? { ...m, recall_card_id: result.card_id } : m)))
        annotationAnalytics.cardCreated({ kind: mark.kind, existing: result.existing, oneTap: true })
        markNotify.cardCreated()
        return true
      } catch (error) {
        if (isNoText(error)) markNotify.cardNoText()
        else if (isRecallUnavailable(error)) markNotify.cardUnavailable()
        else if (documentQuotaExceeded(error)) markNotify.limitReached()
        else markNotify.cardFailed()
        return false
      }
    },
    [commit, flush],
  )

  // ---- What the screen reads ------------------------------------------------------------------------------------------
  const live = useMemo(() => sortMarks(liveMarks(marks)), [marks])
  const info = useMemo(() => localMarksInfo(live.length, serverInfo), [live.length, serverInfo])
  const sync = deriveMarksSync({ online, saving: flushing, queued, parked: parked.length })
  const byId = useMemo(() => new Map(marks.map((m) => [m.id, m])), [marks])
  const find = useCallback((id: string) => byId.get(id), [byId])

  return {
    marks: live,
    all: marks,
    find,
    status,
    online,
    sync,
    queued,
    parked,
    info,
    notice: marksNotice(info),
    add,
    edit,
    remove,
    restore,
    makeCard,
    syncNow,
    applyServerMark,
    refreshQueue,
  }
}
