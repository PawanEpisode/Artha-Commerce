import { useFeatureFlag } from '~/modules/observability'

/** The `today_planner` flag (the study plan, the budget suggestion and the bonus round). Strict, like the API: an outage never opens it. */
export const usePlannerFlag = () => useFeatureFlag('today_planner', { strict: true })
