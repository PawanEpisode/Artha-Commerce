import { type QueryClient, useMutation, useQueryClient } from '@tanstack/react-query'

import { track } from '~/modules/observability'

import { logEvent, newClientId, setChapterExclusion, setConfidence, tickChapter, tickTopic } from '../lib/api'
import { computeComponents, DEFAULT_WEIGHTS, deriveStatus } from '../lib/formula'
import { coverageKeys } from '../lib/keys'
import type {
  ChapterCoverage,
  ChapterRow,
  ChapterState,
  Confidence,
  CoverageSettings,
  EventType,
  Overview,
  SubjectCoverage,
} from '../lib/types'

const MILESTONES = [25, 50, 75, 100]

/** Replace the chapter in every cache that shows it, then refresh what the roll-ups feed. */
function applyState(qc: QueryClient, chapterId: string, state: ChapterState, subjectId?: string) {
  qc.setQueryData<ChapterCoverage>(coverageKeys.chapter(chapterId), (old) =>
    old ? { ...old, chapter: state.chapter } : old,
  )
  if (subjectId) {
    qc.setQueryData<SubjectCoverage>(coverageKeys.subject(subjectId), (old) =>
      old
        ? {
            subject: { ...old.subject, ...state.subject },
            chapters: old.chapters.map((c) => (c.id === chapterId ? state.chapter : c)),
          }
        : old,
    )
  }
  void qc.invalidateQueries({ queryKey: coverageKeys.overview })
  void qc.invalidateQueries({ queryKey: coverageKeys.due })
}

/** Fires `coverage_milestone_reached` once when a roll-up crosses 25, 50, 75 or 100. */
function trackMilestones(scope: 'subject' | 'level', before: number | undefined, after: number) {
  if (before === undefined) return
  for (const m of MILESTONES) if (before < m && after >= m) track('coverage_milestone_reached', { scope, milestone: m })
}

/** Local estimate while the request is in flight, using the same maths as the server. */
function estimate(chapter: ChapterRow, topicsDone: number, weights: CoverageSettings | undefined): ChapterRow {
  const w = weights
    ? { read: weights.w_read, practice: weights.w_practice, revise: weights.w_revise, mock: weights.w_mock }
    : DEFAULT_WEIGHTS
  const c = computeComponents(
    {
      topicsTotal: chapter.topics_total,
      topicsDone,
      practiceCount: chapter.practice_count,
      revisionCount: chapter.revision_count,
      mockCount: chapter.mock_count,
      targetPracticeSets: chapter.targets.practice,
      targetRevisions: chapter.targets.revisions,
      targetMocks: chapter.targets.mocks,
    },
    w,
  )
  return {
    ...chapter,
    topics_done: topicsDone,
    coverage_pct: c.coverage,
    components: { read: c.read, practice: c.practice, revise: c.revise, mock: c.mock },
    status: deriveStatus({
      readPct: c.read,
      coveragePct: c.coverage,
      practiceCount: chapter.practice_count,
      revisionCount: chapter.revision_count,
      anyActivity: topicsDone > 0 || chapter.practice_count + chapter.mock_count + chapter.revision_count > 0,
    }),
  }
}

interface Ctx {
  chapterId: string
  subjectId: string
  subjectKey: string
  chapterKey: string
}

/** Tick or untick one topic (or the chapter itself when it has no topics). Optimistic, idempotent, rolls back on error. */
export function useTickTopic(ctx: Ctx) {
  const qc = useQueryClient()
  const key = coverageKeys.chapter(ctx.chapterId)
  return useMutation({
    mutationFn: ({ topicId, done }: { topicId: string | null; done: boolean }) => {
      const clientId = newClientId()
      return topicId ? tickTopic(topicId, done, clientId) : tickChapter(ctx.chapterId, done, clientId)
    },
    onMutate: async ({ topicId, done }) => {
      await qc.cancelQueries({ queryKey: key })
      const previous = qc.getQueryData<ChapterCoverage>(key)
      if (previous) {
        const topics = previous.topics.map((t) => (t.id === topicId ? { ...t, is_done: done } : t))
        const topicsDone = previous.chapter.has_topics ? topics.filter((t) => t.is_done).length : done ? 1 : 0
        qc.setQueryData<ChapterCoverage>(key, {
          ...previous,
          topics,
          chapter: estimate(previous.chapter, topicsDone, qc.getQueryData(coverageKeys.settings)),
        })
      }
      return { previous, overview: qc.getQueryData<Overview>(coverageKeys.overview) }
    },
    onError: (_e, _v, c) => {
      if (c?.previous) qc.setQueryData(key, c.previous)
    },
    onSuccess: (state, { done }, c) => {
      const prev = c?.overview?.subjects.find((s) => s.id === ctx.subjectId)
      trackMilestones('subject', prev?.pct_simple, state.subject.pct_simple)
      trackMilestones('level', c?.overview?.level.pct_simple, state.level.pct_simple)
      track(done ? 'topic_ticked' : 'topic_unticked', { subject_key: ctx.subjectKey, chapter_key: ctx.chapterKey })
      // Keep the optimistic topic list; take the server's chapter row (the source of truth).
      qc.setQueryData<ChapterCoverage>(key, (old) => (old ? { ...old, chapter: state.chapter } : old))
      applyState(qc, ctx.chapterId, state, ctx.subjectId)
      void qc.invalidateQueries({ queryKey: key })
    },
  })
}

const EVENT_NAME: Record<EventType, string> = {
  practice_done: 'practice_logged',
  mock_done: 'mock_logged',
  revision_done: 'revision_logged',
}

/** Score as a bucket, never the raw number (analytics privacy). */
const scoreBucket = (value: number | null | undefined) =>
  value === null || value === undefined ? 'none' : value < 40 ? 'under_40' : value < 70 ? '40_to_69' : '70_plus'

export function useLogEvent(ctx: Ctx) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ type, value }: { type: EventType; value?: number | null }) =>
      logEvent({ chapter_id: ctx.chapterId, type, value: value ?? null, client_id: newClientId() }),
    onSuccess: (state, { type, value }) => {
      track(EVENT_NAME[type], {
        subject_key: ctx.subjectKey,
        chapter_key: ctx.chapterKey,
        score_bucket: scoreBucket(value),
      })
      applyState(qc, ctx.chapterId, state, ctx.subjectId)
      void qc.invalidateQueries({ queryKey: coverageKeys.chapter(ctx.chapterId) })
    },
  })
}

export function useSetConfidence(ctx: Ctx) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confidence: Confidence | null) => setConfidence(ctx.chapterId, confidence),
    onSuccess: (state, confidence) => {
      track('confidence_set', { rating: confidence ?? 'cleared' })
      applyState(qc, ctx.chapterId, state, ctx.subjectId)
    },
  })
}

export function useSetChapterExclusion(ctx: Ctx) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (excluded: boolean) => setChapterExclusion(ctx.chapterId, excluded),
    onSuccess: (state, excluded) => {
      if (excluded) track('chapter_excluded', { subject_key: ctx.subjectKey })
      applyState(qc, ctx.chapterId, state, ctx.subjectId)
    },
  })
}
