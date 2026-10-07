import { useQuery } from '@tanstack/react-query'

import { useFeatureFlag } from '~/modules/observability'

import { getTodayThought, isNotificationsDisabled } from '../lib/api'
import { notificationKeys } from '../lib/keys'

const FIVE_MINUTES = 5 * 60 * 1000

/**
 * The thought card's data. Asked for once per visit: the server fixes the line for the day, so there is nothing to
 * poll. `off` means show no card at all: the flag is off, the server says notifications are off (403
 * `notifications_disabled`, which includes the student switching the motivation inbox off), or there is no thought.
 */
export function useTodayThought() {
  const flagOn = useFeatureFlag('notifications_ui')
  const query = useQuery({
    queryKey: notificationKeys.thought,
    queryFn: getTodayThought,
    enabled: flagOn,
    staleTime: FIVE_MINUTES,
    retry: (count, error) => !isNotificationsDisabled(error) && count < 2,
  })
  const disabled = !flagOn || isNotificationsDisabled(query.error)
  return {
    thought: query.data ?? null,
    off: disabled || (query.data === null && !query.isPending),
    query,
  }
}
