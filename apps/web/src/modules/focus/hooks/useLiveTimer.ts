import { useQuery } from '@tanstack/react-query'

import { isFeatureDisabled } from '../lib/api'
import { focusKeys } from '../lib/keys'
import { fetchTimerState } from './useFocusTimer'

/**
 * Which timer is running right now, without starting a second heartbeat: it reads the same cache entry the corner
 * mini timer keeps fresh. `live` is `none` until the answer arrives.
 */
export function useLiveTimer() {
  const query = useQuery({
    queryKey: focusKeys.timer,
    queryFn: fetchTimerState,
    retry: (count, error) => !isFeatureDisabled(error) && count < 1,
  })
  return { live: query.data?.live ?? 'none', featureDisabled: isFeatureDisabled(query.error) }
}
