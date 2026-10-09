import type { TodayPlan } from './schemas'

export type HubState = 'vacation' | 'empty' | 'catchup' | 'caught_up' | 'ready'

/** Which version of the hub the plan calls for. The order matters: vacation wins, then "no cards", then catch-up. */
export function hubStateOf(plan: TodayPlan): HubState {
  if (plan.vacation_until && plan.vacation_until >= plan.local_date) return 'vacation'
  const nothing = plan.counts.new + plan.counts.learning + plan.counts.due === 0
  if (nothing && plan.tiles.length === 0 && plan.next_due_at === null && plan.new_available === 0) return 'empty'
  if (plan.catchup.active) return 'catchup'
  if (plan.queue_size === 0) return 'caught_up'
  return 'ready'
}

/** Search params of the review route for a source. */
export const reviewSearch = (source: string, extra: Record<string, string | number | boolean> = {}) => ({
  source,
  ...extra,
})
