import { toast, toastApiError } from '@artha/design-system'

import type { Alert } from './alerts'

/** The one place that words every focus-timer outcome. Toasts say what happened; field problems stay inline. */
const ID = { timer: 'focus-timer', phase: 'focus-phase', settings: 'focus-settings', offline: 'focus-offline' } as const

export const notify = {
  queued: () =>
    toast.info('Saved on this device', { id: ID.offline, description: 'It will sync when you are back online.' }),

  started: (phase: 'focus' | 'short_break' | 'long_break', round: number, queued = false) => {
    if (queued) return notify.queued()
    return phase === 'focus'
      ? toast.success(`Round ${round} started`, { id: ID.timer })
      : toast.info(phase === 'long_break' ? 'Long break started' : 'Break started', { id: ID.timer })
  },
  paused: (queued = false) => (queued ? notify.queued() : toast.info('Timer paused', { id: ID.timer })),
  resumed: (queued = false) => (queued ? notify.queued() : toast.success('Timer resumed', { id: ID.timer })),
  extended: (queued = false) => (queued ? notify.queued() : toast.info('Added 5 minutes', { id: ID.timer })),
  breakSkipped: (queued = false) => (queued ? notify.queued() : toast.info('Break skipped', { id: ID.timer })),
  /** `outcome` is the server's word for what happened to the round. */
  ended: (opts: { saved: boolean; outcome?: string; queued?: boolean }) => {
    if (opts.queued) return notify.queued()
    if (opts.saved && opts.outcome === 'completed') return toast.success('Round saved', { id: ID.timer })
    if (opts.saved && opts.outcome === 'saved') return toast.success('Saved as a partial round', { id: ID.timer })
    if (opts.saved && opts.outcome === 'too_short') return toast.info('Under a minute, so not saved', { id: ID.timer })
    return toast.info('Round discarded', { id: ID.timer, description: 'Nothing was saved.' })
  },
  /** A round or break ran out: "Focus round done" and what comes next. */
  targetReached: (alert: Alert) => toast.success(alert.title, { id: ID.phase, description: alert.body }),
  phaseEnded: (alert: Alert) => toast.success(alert.title, { id: ID.phase, description: alert.body }),
  claimed: (counted: boolean) =>
    counted
      ? toast.success('Round counted', { id: ID.timer })
      : toast.info('Round discarded', { id: ID.timer, description: 'It was not counted.' }),

  settingsSaved: () => toast.success('Settings saved', { id: ID.settings }),
  exportStarted: () => toast.info('Preparing your timer data', { id: 'focus-export' }),
  exportFinished: () => toast.success('Timer data downloaded', { id: 'focus-export' }),
  dataDeleted: () => toast.success('Timer data deleted'),
  notificationsBlocked: () =>
    toast.warning('Notifications are blocked', {
      description: 'Allow them for this site in your browser, then switch this on again.',
    }),

  /** Another device changed the timer first: the screen already shows the latest. */
  outOfDate: () =>
    toast.warning('The timer changed on another device', { id: ID.timer, description: 'Showing the latest.' }),
  error: (error: unknown, fallback: string) => toastApiError(error, fallback),
}
