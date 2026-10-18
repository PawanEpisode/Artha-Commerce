import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as api from '../api'
import type { PaperAnalysisSettings } from '../types'

export const paperAnalysisKeys = {
  all: ['paperanalysis'] as const,
  subjects: (enrollmentId?: string) => [...paperAnalysisKeys.all, 'subjects', enrollmentId] as const,
  priority: (subjectKey?: string, enrollmentId?: string) =>
    [...paperAnalysisKeys.all, 'priority', subjectKey, enrollmentId] as const,
  stats: (subjectKey: string, window?: number) => [...paperAnalysisKeys.all, 'stats', subjectKey, window] as const,
  patterns: (subjectKey: string, window?: number) =>
    [...paperAnalysisKeys.all, 'patterns', subjectKey, window] as const,
  chapterHistory: (chapterKey: string, window?: number) =>
    [...paperAnalysisKeys.all, 'history', chapterKey, window] as const,
  activePlan: () => [...paperAnalysisKeys.all, 'plan', 'active'] as const,
  settings: () => [...paperAnalysisKeys.all, 'settings'] as const,
}

export function useSubjectStatuses(enrollmentId?: string) {
  return useQuery({
    queryKey: paperAnalysisKeys.subjects(enrollmentId),
    queryFn: () => api.fetchSubjectStatuses(enrollmentId),
    staleTime: 60_000,
  })
}

export function usePriority(options?: { subjectKey?: string; enrollmentId?: string; forceRefresh?: boolean }) {
  return useQuery({
    queryKey: paperAnalysisKeys.priority(options?.subjectKey, options?.enrollmentId),
    queryFn: () => api.fetchRecommendations(options),
    staleTime: 300_000,
  })
}

export function useSubjectStats(subjectKey: string, options?: { window?: number }) {
  return useQuery({
    queryKey: paperAnalysisKeys.stats(subjectKey, options?.window),
    queryFn: () => api.fetchSubjectStats(subjectKey, options),
    enabled: Boolean(subjectKey),
    staleTime: 60_000,
  })
}

export function useSubjectPatterns(subjectKey: string, options?: { window?: number }) {
  return useQuery({
    queryKey: paperAnalysisKeys.patterns(subjectKey, options?.window),
    queryFn: () => api.fetchSubjectPatterns(subjectKey, options),
    enabled: Boolean(subjectKey),
    staleTime: 60_000,
  })
}

export function useChapterHistory(chapterKey: string, options?: { window?: number }) {
  return useQuery({
    queryKey: paperAnalysisKeys.chapterHistory(chapterKey, options?.window),
    queryFn: () => api.fetchChapterHistory(chapterKey, options),
    enabled: Boolean(chapterKey),
    staleTime: 60_000,
  })
}

export function useActivePlan() {
  return useQuery({
    queryKey: paperAnalysisKeys.activePlan(),
    queryFn: () => api.fetchActivePlan(),
    staleTime: 30_000,
  })
}

export function usePaperAnalysisSettings() {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: paperAnalysisKeys.settings(),
    queryFn: () => api.fetchSettings(),
    staleTime: 300_000,
  })

  const mutation = useMutation({
    mutationFn: (payload: Partial<PaperAnalysisSettings>) => api.updateSettings(payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(paperAnalysisKeys.settings(), updated)
      queryClient.invalidateQueries({ queryKey: paperAnalysisKeys.all })
    },
  })

  return { ...query, updateSettings: mutation.mutateAsync }
}

export function usePlanMutations() {
  const queryClient = useQueryClient()

  const adoptMutation = useMutation({
    mutationFn: api.adoptPlan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paperAnalysisKeys.activePlan() })
    },
  })

  const replanMutation = useMutation({
    mutationFn: api.replanActivePlan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paperAnalysisKeys.activePlan() })
    },
  })

  const updateItemMutation = useMutation({
    mutationFn: ({ itemId, state }: { itemId: string; state: 'planned' | 'done' | 'skipped' }) =>
      api.updatePlanItem(itemId, { state }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paperAnalysisKeys.activePlan() })
    },
  })

  const endPlanMutation = useMutation({
    mutationFn: api.endActivePlan,
    onSuccess: () => {
      queryClient.setQueryData(paperAnalysisKeys.activePlan(), { plan: null })
      queryClient.invalidateQueries({ queryKey: paperAnalysisKeys.activePlan() })
    },
  })

  return {
    adoptPlan: adoptMutation.mutateAsync,
    replan: replanMutation.mutateAsync,
    updateItem: updateItemMutation.mutateAsync,
    endPlan: endPlanMutation.mutateAsync,
    isAdopting: adoptMutation.isPending,
    isReplanning: replanMutation.isPending,
  }
}
