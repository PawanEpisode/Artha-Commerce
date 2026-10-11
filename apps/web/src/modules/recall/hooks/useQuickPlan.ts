import { useQuery } from '@tanstack/react-query'

import { ApiError } from '~/lib/api'

import { recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'

/** The quick revision plan. `no_exam_date` and `exam_passed` are answers, not failures, so they are not retried. */
export const useQuickPlan = (params: { minutes?: number }, enabled = true) =>
  useQuery({
    queryKey: recallKeys.quickPlan(params),
    queryFn: () => recallApi.quickPlan(params),
    enabled,
    staleTime: 60_000,
    retry: (count, err) => !(err instanceof ApiError && err.status === 422) && count < 2,
  })
