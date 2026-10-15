import { useFeatureFlag } from '~/modules/observability'

/** The `today_plan` flag. Strict like the API: off until PostHog says an explicit true, so an outage never opens the beta. */
export const useTodayFlag = () => useFeatureFlag('today_plan', { strict: true })
