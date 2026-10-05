import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query'

import {
  getBreakdown,
  getGoals,
  getHeatmap,
  getHours,
  getSeries,
  getSettings,
  getSummary,
  getTimeVsCoverage,
  getWeeklySummary,
  isFeatureDisabled,
  listSessions,
  type ReportParams,
} from '../lib/api'
import { nowMs } from '../lib/clock'
import { localDate } from '../lib/duration'
import { trackerKeys } from '../lib/keys'
import type { Group, SplitBy } from '../lib/types'

/** Reports are cached on the server for 60 s (ETag), so the page treats them as fresh for the same time. */
const REPORT_STALE_MS = 60_000
const noRetryWhenOff = (count: number, error: unknown) => !isFeatureDisabled(error) && count < 1

export const useTrackerSettings = () =>
  useQuery({ queryKey: trackerKeys.settings, queryFn: getSettings, retry: noRetryWhenOff })

/** Today's date in the student's tracker time zone, on the server's clock. Falls back to the device zone. */
export function useToday(): string {
  const { data } = useTrackerSettings()
  const tz = data?.tz ?? Intl.DateTimeFormat().resolvedOptions().timeZone
  return localDate(nowMs(), tz)
}

export const useGoals = () => useQuery({ queryKey: trackerKeys.goals, queryFn: getGoals, retry: noRetryWhenOff })

export function useSessionsPage(params: {
  from?: string
  to?: string
  subject_id?: string
  source?: string
  include_notes?: boolean
}) {
  return useInfiniteQuery({
    queryKey: [...trackerKeys.sessions, params],
    queryFn: ({ pageParam }) => listSessions({ ...params, cursor: pageParam, limit: 50 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: noRetryWhenOff,
  })
}

const reportOptions = { staleTime: REPORT_STALE_MS, placeholderData: keepPreviousData, retry: noRetryWhenOff }

export const useSummary = (p: ReportParams & { compare?: boolean }) =>
  useQuery({ queryKey: [...trackerKeys.reports, 'summary', p], queryFn: () => getSummary(p), ...reportOptions })

export const useSeries = (p: ReportParams & { group: Group; by?: SplitBy }) =>
  useQuery({ queryKey: [...trackerKeys.reports, 'series', p], queryFn: () => getSeries(p), ...reportOptions })

export const useBreakdown = (p: ReportParams & { by: SplitBy; parent_id?: string }) =>
  useQuery({ queryKey: [...trackerKeys.reports, 'breakdown', p], queryFn: () => getBreakdown(p), ...reportOptions })

export const useHeatmap = (p: ReportParams) =>
  useQuery({ queryKey: [...trackerKeys.reports, 'heatmap', p], queryFn: () => getHeatmap(p), ...reportOptions })

export const useHours = (p: ReportParams) =>
  useQuery({ queryKey: [...trackerKeys.reports, 'hours', p], queryFn: () => getHours(p), ...reportOptions })

export const useTimeVsCoverage = (p: ReportParams & { subject_id: string | undefined }) =>
  useQuery({
    queryKey: [...trackerKeys.reports, 'time-vs-coverage', p],
    queryFn: () => getTimeVsCoverage({ ...p, subject_id: p.subject_id as string }),
    enabled: !!p.subject_id,
    ...reportOptions,
  })

export const useWeeklySummary = (weekStart?: string) =>
  useQuery({
    queryKey: [...trackerKeys.reports, 'weekly', weekStart ?? 'last'],
    queryFn: () => getWeeklySummary(weekStart),
    ...reportOptions,
  })
