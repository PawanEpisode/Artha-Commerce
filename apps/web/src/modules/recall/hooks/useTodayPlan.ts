import { useQuery } from '@tanstack/react-query'

import { recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'

/** Today's plan: counts, limits, catch-up, streak and the forgotten list. Fresh for a minute; a review invalidates it. */
export const useTodayPlan = (enabled = true) =>
  useQuery({ queryKey: recallKeys.today, queryFn: () => recallApi.today(), enabled, staleTime: 60_000 })
