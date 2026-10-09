import { useQuery } from '@tanstack/react-query'

import { recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'

export const useForgotten = (params: { subject_key?: string; limit?: number } = {}, enabled = true) =>
  useQuery({
    queryKey: recallKeys.forgotten(params),
    queryFn: () => recallApi.forgotten(params),
    enabled,
    staleTime: 60_000,
  })
