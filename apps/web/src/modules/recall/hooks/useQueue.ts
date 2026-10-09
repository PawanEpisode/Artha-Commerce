import { useQuery } from '@tanstack/react-query'

import { type QueueParams, type QueueSource, recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'

/** A queue from the server (Review screens use `useReviewSession`, which also reads the stored pack). */
export const useQueue = (source: QueueSource, params: QueueParams = {}, enabled = true) =>
  useQuery({
    queryKey: recallKeys.queue(source, params),
    queryFn: () => recallApi.queue(source, params),
    enabled,
    staleTime: 0,
  })
