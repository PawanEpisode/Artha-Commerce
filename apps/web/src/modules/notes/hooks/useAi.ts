import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useFeatureFlag } from '~/modules/observability'

import {
  acceptSummary,
  cancelAiOcr,
  cancelSummary,
  discardSummary,
  getAiConsent,
  getAiOcr,
  getSummary,
  grantAiConsent,
  latestSummary,
  requestAiOcr,
  requestSummary,
  withdrawAiConsent,
} from '../lib/ai-api'
import { type AiFailure, classifyAiError } from '../lib/ai-errors'
import { type AiOcrStarted, isSummaryActive, type SummaryJob } from '../lib/ai-types'
import { newClientId } from '../lib/api'
import { notesKeys } from '../lib/keys'
import { useNotesSettings } from './useNotesSettings'

/** AI help is on for this student only when PostHog says so (fail closed) and the server says it is switched on. */
export function useAiAvailable() {
  const flag = useFeatureFlag('notes_ai', { strict: true })
  const settings = useNotesSettings(flag)
  return {
    flag,
    available: flag && settings.data?.capabilities?.ai_summary === true,
    loading: flag && settings.isPending,
  }
}

export const useAiConsent = (enabled = true) =>
  useQuery({ queryKey: notesKeys.aiConsent, queryFn: getAiConsent, enabled, staleTime: 60_000 })

export function useGrantConsent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (version: string) => grantAiConsent(version),
    onSuccess: (consent) => qc.setQueryData(notesKeys.aiConsent, consent),
  })
}

export function useWithdrawConsent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: withdrawAiConsent,
    onSuccess: (report) => {
      qc.setQueryData(notesKeys.aiConsent, report.consent)
      void qc.invalidateQueries({ queryKey: notesKeys.summaries })
      void qc.invalidateQueries({ queryKey: notesKeys.usage })
    },
  })
}

/** One summary job. While it is queued or running it is read again every 4 seconds; then it stops. */
export const useSummary = (id: string) =>
  useQuery({
    queryKey: notesKeys.summary(id),
    queryFn: () => getSummary(id),
    refetchInterval: (query) => {
      const job = query.state.data
      return job && isSummaryActive(job.status) ? 4000 : false
    },
  })

export const useChapterSummary = (chapterId: string | undefined, enabled: boolean) =>
  useQuery({
    queryKey: notesKeys.chapterSummary(chapterId ?? ''),
    queryFn: () => latestSummary(chapterId ?? ''),
    enabled: enabled && !!chapterId,
    select: (data) => data.job,
  })

export type StartResult = { ok: true; job: SummaryJob } | { ok: false; failure: AiFailure }

/** Asks for a summary. Never throws: the screen branches on the result. A fresh client id makes a retry safe. */
export function useStartSummary() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (chapterId: string): Promise<StartResult> => {
      try {
        const job = await requestSummary({ client_id: newClientId(), chapter_id: chapterId })
        qc.setQueryData(notesKeys.summary(job.id), job)
        void qc.invalidateQueries({ queryKey: notesKeys.usage })
        return { ok: true, job }
      } catch (error) {
        return { ok: false, failure: classifyAiError(error) }
      }
    },
  })
}

function useJobAction<T>(fn: (id: string) => Promise<T>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notesKeys.summaries })
      void qc.invalidateQueries({ queryKey: notesKeys.usage })
    },
  })
}

export const useDiscardSummary = () => useJobAction(discardSummary)
export const useCancelSummary = () => useJobAction(cancelSummary)

export function useAcceptSummary() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; title?: string; body_md?: string }) => acceptSummary(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notesKeys.summaries })
      void qc.invalidateQueries({ queryKey: notesKeys.all })
    },
  })
}

export type AiOcrStart = { ok: true; started: AiOcrStarted } | { ok: false; failure: AiFailure }

/** Asks AI to read one page of a document. Never throws; the screen branches on the result. */
export function useRequestAiOcr() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ docId, page }: { docId: string; page: number }): Promise<AiOcrStart> => {
      try {
        const started = await requestAiOcr(docId, String(page))
        if (started.job) qc.setQueryData(notesKeys.aiOcr(started.job.id), started.job)
        void qc.invalidateQueries({ queryKey: notesKeys.usage })
        return { ok: true, started }
      } catch (error) {
        return { ok: false, failure: classifyAiError(error) }
      }
    },
  })
}

/** An AI page read, read again every 3 seconds until it ends. */
export const useAiOcrJob = (jobId: string | undefined) =>
  useQuery({
    queryKey: notesKeys.aiOcr(jobId ?? ''),
    queryFn: () => getAiOcr(jobId ?? ''),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const job = query.state.data
      return job && isSummaryActive(job.status) ? 3000 : false
    },
  })

export function useCancelAiOcr() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: cancelAiOcr,
    onSuccess: (job) => {
      qc.setQueryData(notesKeys.aiOcr(job.id), job)
      void qc.invalidateQueries({ queryKey: notesKeys.usage })
    },
  })
}
