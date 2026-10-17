import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { analyticsApi } from '../lib/api'
import type { GroupByOption, RangeWindow, SettingsData } from '../lib/types'

const ANALYTICS_QUERY_KEYS = {
  all: ['analytics'] as const,
  overview: (range: RangeWindow) => [...ANALYTICS_QUERY_KEYS.all, 'overview', range] as const,
  performance: (by: GroupByOption, range: RangeWindow) =>
    [...ANALYTICS_QUERY_KEYS.all, 'performance', by, range] as const,
  trends: (window: RangeWindow) => [...ANALYTICS_QUERY_KEYS.all, 'trends', window] as const,
  weakTopics: (limit: number) => [...ANALYTICS_QUERY_KEYS.all, 'weakTopics', limit] as const,
  speed: (range: RangeWindow) => [...ANALYTICS_QUERY_KEYS.all, 'speed', range] as const,
  mistakes: (range: RangeWindow) => [...ANALYTICS_QUERY_KEYS.all, 'mistakes', range] as const,
  readiness: () => [...ANALYTICS_QUERY_KEYS.all, 'readiness'] as const,
  reports: () => [...ANALYTICS_QUERY_KEYS.all, 'reports'] as const,
  goals: () => [...ANALYTICS_QUERY_KEYS.all, 'goals'] as const,
  settings: () => [...ANALYTICS_QUERY_KEYS.all, 'settings'] as const,
  share: (token: string) => [...ANALYTICS_QUERY_KEYS.all, 'share', token] as const,
}

export function useAnalyticsOverview(range: RangeWindow = '30d', enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.overview(range),
    queryFn: () => analyticsApi.getOverview(range),
    enabled,
    staleTime: 60_000,
  })
}

export function usePerformance(by: GroupByOption = 'chapter', range: RangeWindow = '30d', enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.performance(by, range),
    queryFn: () => analyticsApi.getPerformance(by, range),
    enabled,
    staleTime: 60_000,
  })
}

export function useTrends(window: RangeWindow = '30d', enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.trends(window),
    queryFn: () => analyticsApi.getTrends(window),
    enabled,
    staleTime: 60_000,
  })
}

export function useWeakTopics(limit = 8, enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.weakTopics(limit),
    queryFn: () => analyticsApi.getWeakTopics(limit),
    enabled,
    staleTime: 60_000,
  })
}

export function useSpeed(range: RangeWindow = '30d', enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.speed(range),
    queryFn: () => analyticsApi.getSpeed(range),
    enabled,
    staleTime: 60_000,
  })
}

export function useMistakes(range: RangeWindow = '30d', enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.mistakes(range),
    queryFn: () => analyticsApi.getMistakes(range),
    enabled,
    staleTime: 60_000,
  })
}

export function useReadiness(enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.readiness(),
    queryFn: () => analyticsApi.getReadiness(),
    enabled,
    staleTime: 60_000,
  })
}

export function useReports(enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.reports(),
    queryFn: () => analyticsApi.listReports(),
    enabled,
    staleTime: 30_000,
  })
}

export function useSettings(enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.settings(),
    queryFn: () => analyticsApi.getSettings(),
    enabled,
  })
}

export function usePublicShare(token: string, enabled = true) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.share(token),
    queryFn: () => analyticsApi.getPublicShare(token),
    enabled: enabled && Boolean(token),
    staleTime: 300_000,
  })
}

export function useRefreshAnalytics() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (limit?: number) => analyticsApi.refreshAnalytics(limit),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ANALYTICS_QUERY_KEYS.all })
    },
    meta: {
      successMessage: 'Analytics updated successfully',
      errorMessage: 'Could not refresh analytics. Please try again.',
    },
  })
}

export function useBuildFixSet() {
  return useMutation({
    mutationFn: (payload: { topic_id?: string; chapter_id?: string; limit?: number }) =>
      analyticsApi.buildFixSet(payload),
    meta: {
      successMessage: 'Practice drill created successfully',
      errorMessage: 'Could not create practice drill.',
    },
  })
}

export function useCreateReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: analyticsApi.createReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ANALYTICS_QUERY_KEYS.reports() })
    },
    meta: {
      successMessage: 'Report generated successfully',
      errorMessage: 'Could not generate report.',
    },
  })
}

export function useCreateShare() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: analyticsApi.createShare,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ANALYTICS_QUERY_KEYS.reports() })
    },
    meta: {
      successMessage: 'Share link generated',
      errorMessage: 'Could not generate share link.',
    },
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Partial<SettingsData>) => analyticsApi.updateSettings(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ANALYTICS_QUERY_KEYS.settings() })
    },
    meta: {
      successMessage: 'Settings updated successfully',
      errorMessage: 'Could not update settings.',
    },
  })
}
