import { useQuery } from '@tanstack/react-query'

import { fetchMyCardDetail, isFeatureDisabled } from '../lib/api'
import { amendmentsKeys } from '../lib/keys'
import type { MyCard } from '../lib/types'

export function useMyCardDetail(publicId: string | null | undefined, enabled = true) {
  return useQuery<MyCard>({
    queryKey: amendmentsKeys.cardDetail(publicId ?? ''),
    queryFn: () => {
      if (!publicId) {
        throw new Error('publicId is required to fetch card details')
      }
      return fetchMyCardDetail(publicId)
    },
    enabled: Boolean(publicId) && enabled,
    staleTime: 60_000,
    retry: (count, error) => !isFeatureDisabled(error) && count < 2,
  })
}
