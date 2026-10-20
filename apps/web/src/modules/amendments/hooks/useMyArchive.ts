import { useQuery } from '@tanstack/react-query'

import { fetchMyArchive, isFeatureDisabled } from '../lib/api'
import { amendmentsKeys } from '../lib/keys'
import type { TermArchiveRow } from '../lib/types'

export function useMyArchive(enabled = true) {
  return useQuery<TermArchiveRow[]>({
    queryKey: amendmentsKeys.archive(),
    queryFn: fetchMyArchive,
    enabled,
    staleTime: 60_000,
    retry: (count, error) => !isFeatureDisabled(error) && count < 2,
  })
}
