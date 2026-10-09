import { useQuery } from '@tanstack/react-query'

import { recallApi, type StatsRange } from '../lib/api'
import { recallKeys } from '../lib/keys'

/** Reports are cached on the server by ETag (the browser revalidates for free), so a short stale time is enough. */
const STALE = 60_000

export const useStatsSummary = (range: StatsRange, enabled = true) =>
  useQuery({
    queryKey: recallKeys.stats('summary', { range }),
    queryFn: () => recallApi.statsSummary(range),
    enabled,
    staleTime: STALE,
  })
export const useStatsRetention = (range: StatsRange, enabled = true) =>
  useQuery({
    queryKey: recallKeys.stats('retention', { range }),
    queryFn: () => recallApi.statsRetention(range),
    enabled,
    staleTime: STALE,
  })
export const useStatsForecast = (days = 30, enabled = true) =>
  useQuery({
    queryKey: recallKeys.stats('forecast', { days }),
    queryFn: () => recallApi.statsForecast(days),
    enabled,
    staleTime: STALE,
  })
export const useStatsChapters = (enabled = true) =>
  useQuery({
    queryKey: recallKeys.stats('chapters'),
    queryFn: recallApi.statsChapters,
    enabled,
    staleTime: STALE,
  })
