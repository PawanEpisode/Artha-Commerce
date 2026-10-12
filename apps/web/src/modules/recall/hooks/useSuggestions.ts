import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { trackRecall } from '../lib/analytics'
import { recallApi, type SuggestionRequestBody } from '../lib/api'
import { recallKeys } from '../lib/keys'
import type { Suggestion, SuggestionBatch } from '../lib/schemas'
import { isActive, pollInterval } from '../lib/suggestions'
import { useRefresh } from './useCardScreens'

/** The `recall_ai` flag (AI card suggestions), fail closed like the API: it costs money and sends her text to Google. */
export const useRecallAiEnabled = () => useFeatureFlag('recall_ai', { strict: true })

export const useAiOverview = (enabled = true) =>
  useQuery({ queryKey: recallKeys.aiOverview, queryFn: recallApi.aiOverview, enabled })

export const useAiConsent = (enabled = true) =>
  useQuery({ queryKey: recallKeys.aiConsent, queryFn: recallApi.aiConsent, enabled })

export function useGrantAiConsent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (version: string) => recallApi.grantAiConsent(version),
    onSuccess: () => {
      trackRecall('recall_ai_consent_given', {})
      void qc.invalidateQueries({ queryKey: ['recall', 'ai'] })
    },
  })
}

export function useWithdrawAiConsent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => recallApi.withdrawAiConsent(),
    onSuccess: (r) => {
      trackRecall('recall_ai_consent_withdrawn', { drafts_deleted: r.drafts_deleted })
      void qc.invalidateQueries({ queryKey: ['recall', 'ai'] })
    },
  })
}

/**
 * Asking for suggestions. One id per request: a second tap or a retry after a dropped answer joins the same batch instead of
 * paying twice. `fresh()` starts a new id once she changes what she is asking for.
 */
export function useRequestSuggestions() {
  const qc = useQueryClient()
  const id = useRef(crypto.randomUUID())
  const mutation = useMutation({
    mutationFn: (body: Omit<SuggestionRequestBody, 'client_id'>) =>
      recallApi.requestSuggestions({ ...body, client_id: id.current }),
    onSuccess: (batch, body) => {
      trackRecall('recall_suggestions_requested', {
        count: body.count ?? batch.requested_count,
        sources: body.sources.length,
        reused: batch.reused ? 1 : 0,
      })
      qc.setQueryData(recallKeys.suggestionBatch(batch.id), batch)
      void qc.invalidateQueries({ queryKey: recallKeys.aiOverview })
      void qc.invalidateQueries({ queryKey: ['recall', 'ai', 'batches'] })
    },
  })
  return { ...mutation, fresh: () => void (id.current = crypto.randomUUID()) }
}

/** One batch, read again every few seconds while the model works and never after it is finished. */
export function useSuggestionBatch(id: string | undefined) {
  const started = useRef(Date.now())
  const qc = useQueryClient()
  return useQuery({
    queryKey: recallKeys.suggestionBatch(id ?? 'none'),
    queryFn: async () => {
      const batch = await recallApi.suggestionBatch(id as string)
      if (!isActive(batch)) {
        trackRecall('recall_suggestions_ready', { produced: batch.produced, dropped: batch.dropped })
        void qc.invalidateQueries({ queryKey: recallKeys.aiOverview })
      }
      return batch
    },
    enabled: Boolean(id),
    refetchInterval: (q) => pollInterval(q.state.data, Date.now() - started.current) ?? false,
  })
}

export const useSuggestionBatches = (chapterId?: string) =>
  useQuery({ queryKey: recallKeys.suggestionBatches(chapterId), queryFn: () => recallApi.suggestionBatches(chapterId) })

function useReplaceSuggestion() {
  const qc = useQueryClient()
  return (batchId: string, next: Suggestion) =>
    qc.setQueryData<SuggestionBatch>(recallKeys.suggestionBatch(batchId), (b) =>
      b ? { ...b, suggestions: b.suggestions.map((s) => (s.id === next.id ? next : s)) } : b,
    )
}

export function useAcceptSuggestion(batchId: string) {
  const refresh = useRefresh()
  const replace = useReplaceSuggestion()
  return useMutation({
    mutationFn: (v: { id: string; fields?: Record<string, string>; force?: boolean }) =>
      recallApi.acceptSuggestion(v.id, { fields: v.fields, force: v.force }),
    onSuccess: (r) => {
      const edited = r.suggestion.status === 'edited_accepted' ? 1 : 0
      trackRecall('recall_suggestion_decided', { decision: 'accepted', edited })
      replace(batchId, r.suggestion)
      refresh()
    },
  })
}

export function useRejectSuggestion(batchId: string) {
  const replace = useReplaceSuggestion()
  return useMutation({
    mutationFn: (id: string) => recallApi.rejectSuggestion(id),
    onSuccess: (r) => {
      trackRecall('recall_suggestion_decided', { decision: 'rejected', edited: 0 })
      replace(batchId, r.suggestion)
    },
  })
}
