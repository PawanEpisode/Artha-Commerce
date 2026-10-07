import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useFeatureFlag } from '~/modules/observability'

import { getDigest, isNotificationsDisabled, postDigestAnswer } from '../lib/api'
import { notificationKeys } from '../lib/keys'
import type { DigestAnswer } from '../lib/schemas'

/** The digest offer and switch (W3.7). Answering refreshes what the switch changes: settings and the category grid. */
export function useDigest() {
  const qc = useQueryClient()
  const flagOn = useFeatureFlag('notifications_ui')
  const query = useQuery({
    queryKey: notificationKeys.digest,
    queryFn: getDigest,
    enabled: flagOn,
    retry: (count, error) => !isNotificationsDisabled(error) && count < 2,
  })
  const answer = useMutation({
    mutationFn: (choice: DigestAnswer) => postDigestAnswer(choice),
    onSuccess: async (state, choice) => {
      qc.setQueryData(notificationKeys.digest, state)
      if (choice === 'accept' || choice === 'stop') {
        await Promise.all([
          qc.invalidateQueries({ queryKey: notificationKeys.categories }),
          qc.invalidateQueries({ queryKey: notificationKeys.settings }),
        ])
      }
    },
  })
  return { flagOn, query, answer }
}
