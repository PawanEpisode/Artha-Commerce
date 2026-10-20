import { useQuery } from '@tanstack/react-query'

import { fetchMySummary, isFeatureDisabled } from '../lib/api'
import { amendmentsKeys } from '../lib/keys'
import type { MySummary } from '../lib/types'

export function useMySummary(enabled = true) {
  return useQuery<MySummary>({
    queryKey: amendmentsKeys.summary(),
    queryFn: fetchMySummary,
    enabled,
    staleTime: 60_000,
    retry: (count, error) => !isFeatureDisabled(error) && count < 2,
  })
}
