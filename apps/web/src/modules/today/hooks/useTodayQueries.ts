import { useQuery, useQueryClient } from '@tanstack/react-query'

import { getPlanFor, getPreview, getSettings, isFeatureDisabled, syncThenOpen } from '../lib/api'
import { todayKeys } from '../lib/keys'
import { isLite, networkHints } from '../lib/lite'
import type { TodaySettings } from '../lib/types'

/** Today's plan. `open/` is idempotent and also reconciles finished work, so it is both the first load and every refresh. */
export function useTodayPlan(enabled = true) {
  const qc = useQueryClient()
  return useQuery({
    queryKey: todayKeys.plan,
    // The smaller payload when the student's setting or the network asks for it (settings may still be loading: then the network decides).
    queryFn: () => syncThenOpen(isLite(qc.getQueryData<TodaySettings>(todayKeys.settings)?.lite_mode, networkHints())),
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    retry: (count, error) => !isFeatureDisabled(error) && count < 2,
  })
}

export const useTodaySettings = (enabled = true) =>
  useQuery({ queryKey: todayKeys.settings, queryFn: getSettings, enabled, staleTime: 5 * 60_000 })

/** What a later day would hold. Read only; the server computes and throws it away. */
export const useDayPreview = (date: string | null) =>
  useQuery({
    queryKey: todayKeys.preview(date ?? ''),
    queryFn: () => getPreview(date as string),
    enabled: date !== null,
    staleTime: 60_000,
    retry: false,
  })

/** A stored plan of an earlier day (read only). 404 means there was none. */
export const useDayPlan = (date: string | null) =>
  useQuery({
    queryKey: todayKeys.day(date ?? ''),
    queryFn: () => getPlanFor(date as string),
    enabled: date !== null,
    staleTime: 60_000,
    retry: false,
  })
