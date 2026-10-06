import type { FocusTimer } from './types'

export interface Alert {
  title: string
  body: string
}

/** What to tell the student when `prev` ended and `next` took its place. Null when nothing ended. Pure. */
export function describeTransition(prev: FocusTimer | null, next: FocusTimer | null): Alert | null {
  if (!prev) return null
  const same = next?.client_id === prev.client_id
  if (same) {
    return next?.status === 'away' && prev.status !== 'away'
      ? { title: 'Did you finish the round?', body: 'You were away when it ended. Tell us whether to count it.' }
      : null
  }
  if (prev.phase === 'focus')
    return next
      ? {
          title: 'Focus round done',
          body: next.phase === 'long_break' ? 'Take a long break. You earned it.' : 'Time for a short break.',
        }
      : { title: 'Focus round done', body: 'Start your break when you are ready.' }
  return next
    ? { title: 'Break is over', body: `Round ${next.round_number} of ${next.rounds_before_long} has started.` }
    : { title: 'Break is over', body: 'Ready for the next round?' }
}

/** The planned length was reached and the round keeps running: tell the student once, without ending anything. */
export const TARGET_REACHED: Alert = {
  title: 'Round target reached',
  body: 'Keep going, or press Stop and save when you are done. Your break starts then.',
}
