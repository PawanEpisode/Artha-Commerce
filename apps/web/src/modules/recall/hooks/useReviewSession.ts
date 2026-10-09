import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { trackRecall } from '../lib/analytics'
import { QUEUE_SOURCES, type QueueParams, type QueueSource, recallApi, type ReviewMode } from '../lib/api'
import { nowDate, nowMs } from '../lib/clock'
import { deviceId, tzOffsetMin } from '../lib/device'
import { eventStore, type LocalMemory, type LocalSummary, QuotaError } from '../lib/eventStore'
import { recallKeys } from '../lib/keys'
import {
  aheadFromPack,
  answer as answerCard,
  currentCard,
  doneCount,
  drop,
  extend,
  isFinished,
  planFromPack,
  type PlayerCard,
  playerCardOf,
  type PlayerState,
  previewLabels,
  type Rating,
  remaining,
  type Scheduler,
  schedulerOf,
  startPlayer,
  undo as undoAnswer,
  undoable,
} from '../lib/player'
import type { ApiPack } from '../lib/schemas'
import { usePack } from './usePack'
import { useOnlineStatus, useRecallUser } from './useRecallBasics'
import { useSync } from './useSync'

export type SessionStatus = 'loading' | 'ready' | 'empty' | 'finished' | 'error'

export interface ReviewParams {
  source: QueueSource
  chapter_id?: string
  deck_id?: string
  kind?: string
  tier?: string
  /** How many cards at most. */
  n?: number
  /** Keep using this session id (a reload of the review URL carries on the same session). */
  sessionId?: string
}

export const isQueueSource = (v: unknown): v is QueueSource =>
  (QUEUE_SOURCES as readonly string[]).includes(v as string)

const memoryOf = (c: PlayerCard): LocalMemory => ({
  state: c.memory.phase,
  stability: c.memory.stability,
  difficulty: c.memory.difficulty,
  due_scheduled_at: c.dueScheduledAt?.toISOString() ?? null,
  postponed_until: c.postponedUntil?.toISOString() ?? null,
  due_at: c.dueAt?.toISOString() ?? null,
  last_review_at: c.memory.lastReviewAt?.toISOString() ?? null,
  reps: c.memory.reps,
  lapses: c.memory.lapses,
  step: c.memory.step,
})

export interface ReviewSession {
  status: SessionStatus
  sessionId: string
  card: PlayerCard | null
  flipped: boolean
  flip: () => void
  /** What each answer would schedule, or null when the student turned intervals off. */
  previews: Record<Rating, string> | null
  rate: (rating: Rating) => Promise<void>
  canUndo: boolean
  undo: () => Promise<boolean>
  done: number
  total: number
  left: number
  catchup: boolean
  offline: boolean
  /** The pack is older than 48 hours. */
  staleWarning: boolean
  /** This device holds as many unsynced reviews as it keeps; no more can be added until it syncs. */
  quotaFull: boolean
  pending: number
  gestures: boolean
  summary: LocalSummary | null
  canReviewAhead: boolean
  reviewAhead: () => void
  hold: (action: 'bury' | 'suspend') => Promise<boolean>
  restart: () => void
}

/**
 * The review player, local first. Cards and their memory come from the stored pack (or the server queue for a chapter, a
 * deck or the forgotten list); every answer is computed here with the scheduler twin, written to IndexedDB, and shown as
 * the next card without waiting for the network. `useSync` sends the events in the background.
 */
export function useReviewSession(params: ReviewParams, enabled = true): ReviewSession {
  const userId = useRecallUser()
  const online = useOnlineStatus()
  const qc = useQueryClient()
  const sync = useSync(enabled)
  const packState = usePack(enabled)
  const { pack } = packState

  const [state, setState] = useState<PlayerState | null>(null)
  const [status, setStatus] = useState<SessionStatus>('loading')
  const [flipped, setFlipped] = useState(false)
  const [quotaFull, setQuotaFull] = useState(false)
  const [catchup, setCatchup] = useState(false)
  const [summary, setSummary] = useState<LocalSummary | null>(null)
  const [round, setRound] = useState(0)

  const stateRef = useRef<PlayerState | null>(null)
  const sessionId = useMemo(() => (round === 0 && params.sessionId) || crypto.randomUUID(), [round]) // eslint-disable-line react-hooks/exhaustive-deps
  const shownAt = useRef(nowMs())
  const started = useRef<number | null>(null)
  const firstAnswer = useRef<number | null>(null)
  const packRef = useRef<ApiPack | null>(null)
  packRef.current = pack
  const sched: Scheduler | null = useMemo(() => (pack ? schedulerOf(pack.settings, pack.weights) : null), [pack])
  const schedRef = useRef<Scheduler | null>(null)
  schedRef.current = sched
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const put = useCallback((next: PlayerState | null) => {
    stateRef.current = next
    setState(next)
  }, [])

  // Build the session once per round, as soon as the pack (and for server-ordered sources, the queue) is in.
  useEffect(() => {
    if (!enabled || !userId) return
    if (started.current === round) return
    if (!pack) {
      if (packState.error) setStatus('error')
      return
    }
    started.current = round
    void (async () => {
      try {
        const now = nowDate()
        let cards: PlayerCard[]
        let isCatchup = false
        let catchupDue = 0
        let overdue = 0
        if (params.source === 'today' && (!online || pack.cards.length > 0)) {
          const plan = planFromPack(pack, now, params.n ?? 50)
          cards = plan.cards
          isCatchup = plan.catchup.active
          catchupDue = plan.catchup.dueCount
          overdue = plan.catchup.oldestOverdueDays
        } else {
          const { source, n, sessionId: _resume, ...rest } = params
          const queueParams: QueueParams = { ...rest, limit: n ?? 20 }
          const queue = await recallApi.queue(source, queueParams)
          const mode: ReviewMode = source === 'catchup' ? 'catchup' : 'normal'
          cards = queue.cards.map((c) => playerCardOf(c, mode))
          isCatchup = source === 'catchup'
        }
        if (!alive.current) return
        setCatchup(isCatchup)
        if (cards.length === 0) {
          setStatus('empty')
          return
        }
        put(startPlayer(cards))
        shownAt.current = nowMs()
        setStatus('ready')
        trackRecall('recall_session_started', {
          source: params.source,
          mode: isCatchup ? 'catchup' : 'normal',
          planned: cards.length,
          offline: !online,
        })
        if (isCatchup) {
          trackRecall('recall_catchup_started', {
            due_total: catchupDue,
            overdue_days_max: Math.round(overdue),
            queue_size: cards.length,
          })
        }
      } catch {
        if (alive.current) setStatus('error')
      }
    })()
    // The session is built once per round; later pack refreshes must not reshuffle a session in progress.
  }, [enabled, userId, pack, round]) // eslint-disable-line react-hooks/exhaustive-deps

  const card = state ? currentCard(state) : null
  useEffect(() => {
    shownAt.current = nowMs()
  }, [card?.id, state?.answered])

  const previews = useMemo(
    () => (card && sched && pack?.settings.show_intervals !== false ? previewLabels(card, nowDate(), sched) : null),
    [card, sched, pack?.settings.show_intervals],
  )

  const finish = useCallback(
    async (finalState: PlayerState) => {
      if (!userId) return
      const done: LocalSummary = {
        reviewed: finalState.answered,
        newCards: finalState.newSeen,
        ratings: finalState.ratings,
        activeSeconds: firstAnswer.current === null ? 0 : Math.round((nowMs() - firstAnswer.current) / 1000),
      }
      setSummary(done)
      const row = await eventStore.getSession(sessionId)
      if (row) await eventStore.saveSession({ ...row, closed: true, summary: done })
      setStatus('finished')
      void sync.syncNow().then(() => qc.invalidateQueries({ queryKey: recallKeys.all }))
    },
    [userId, sessionId, sync, qc],
  )

  const rate = useCallback(
    async (rating: Rating) => {
      const s = stateRef.current
      const sc = schedRef.current
      if (!s || !sc || !userId || !currentCard(s)) return
      const now = nowDate()
      const result = answerCard(s, rating, {
        now,
        durationMs: nowMs() - shownAt.current,
        sessionId,
        deviceId: deviceId(),
        newId: () => crypto.randomUUID(),
        tzOffsetMin: tzOffsetMin(now),
        sched: sc,
      })
      if (!result) return
      try {
        await eventStore.addEvent(userId, result.event)
      } catch (error) {
        if (error instanceof QuotaError) {
          setQuotaFull(true)
          return
        }
        throw error
      }
      const after = result.state.cards[result.event.card_id]
      if (after) await eventStore.saveLocalCard(userId, after.id, memoryOf(after), now.getTime())
      const existing = await eventStore.getSession(sessionId)
      if (!existing) {
        firstAnswer.current = nowMs()
        await eventStore.saveSession({
          id: sessionId,
          userId,
          source: params.source,
          startedAt: now.getTime(),
          plannedCount: s.total,
          opened: false,
          closed: false,
          closeSent: false,
          summary: null,
        })
      }
      put(result.state)
      setFlipped(false)
      if (isFinished(result.state)) await finish(result.state)
      else if (online && result.state.answered % 5 === 0) void sync.syncNow()
    },
    [userId, sessionId, params.source, online, finish, sync, put],
  )

  const undo = useCallback(async (): Promise<boolean> => {
    const s = stateRef.current
    if (!s || !userId) return false
    const now = nowDate()
    const result = undoAnswer(s, now)
    if (!result) return false
    const { undone } = result
    const waiting = (await eventStore.pendingEvents(userId)).some((e) => e.id === undone.eventId)
    if (waiting) {
      await eventStore.removeEvents([undone.eventId])
    } else {
      try {
        await recallApi.undo(crypto.randomUUID(), undone.eventId)
      } catch {
        return false
      }
    }
    await eventStore.saveLocalCard(userId, undone.cardId, memoryOf(undone.before), now.getTime())
    trackRecall('recall_review_undone', { within_seconds: Math.round((now.getTime() - undone.at) / 1000) })
    put(result.state)
    setFlipped(false)
    if (status === 'finished') setStatus('ready')
    return true
  }, [userId, status, put])

  const hold = useCallback(
    async (action: 'bury' | 'suspend'): Promise<boolean> => {
      const s = stateRef.current
      const c = s ? currentCard(s) : null
      if (!s || !c) return false
      try {
        await recallApi.cardAction(c.id, action)
      } catch {
        return false
      }
      const next = drop(s, c.id)
      put(next)
      setFlipped(false)
      if (isFinished(next)) await finish(next)
      return true
    },
    [put, finish],
  )

  const reviewAhead = useCallback(() => {
    const s = stateRef.current
    const p = packRef.current
    if (!p) return
    const ahead = aheadFromPack(p, nowDate(), new Set(s ? Object.keys(s.cards) : []))
    if (ahead.length === 0) return
    put(s ? extend(s, ahead) : startPlayer(ahead))
    shownAt.current = nowMs()
    setStatus('ready')
  }, [put])

  const restart = useCallback(() => {
    put(null)
    setStatus('loading')
    setFlipped(false)
    setSummary(null)
    firstAnswer.current = null
    setRound((r) => r + 1)
  }, [put])

  return {
    status,
    sessionId,
    card,
    flipped,
    flip: useCallback(() => setFlipped(true), []),
    previews,
    rate,
    canUndo: state ? undoable(state, nowDate()) !== null : false,
    undo,
    done: state ? doneCount(state) : 0,
    total: state?.total ?? 0,
    left: state ? remaining(state) : 0,
    catchup,
    offline: !online,
    staleWarning: packState.stale,
    quotaFull,
    pending: sync.pending,
    gestures: pack?.settings.gestures ?? true,
    summary,
    canReviewAhead: pack !== null && status !== 'loading',
    reviewAhead,
    hold,
    restart,
  }
}
