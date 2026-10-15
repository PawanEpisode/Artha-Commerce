import { useQuery } from '@tanstack/react-query'

import { isFeatureDisabled, openToday } from '../lib/api'
import { todayKeys } from '../lib/keys'

/** Today's plan. `open/` is idempotent and also reconciles finished work, so it is both the first load and every refresh. */
export function useTodayPlan(enabled = true) {
  return useQuery({
    queryKey: todayKeys.plan,
    queryFn: openToday,
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    retry: (count, error) => !isFeatureDisabled(error) && count < 2,
  })
}
