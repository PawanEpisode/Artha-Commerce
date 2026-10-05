import { toast, toastApiError } from '@artha/design-system'

import { formatDuration } from './duration'

/** The one place that words every tracker outcome. Toasts say what happened; field problems stay inline. */
const ID = { stopwatch: 'tracker-stopwatch', offline: 'tracker-offline', sync: 'tracker-sync' } as const

const QUEUED_TITLE = 'Saved on this device'
const QUEUED_BODY = 'It will sync when you are back online.'

export interface UndoAction {
  label: 'Undo'
  onClick: () => void
}

const undo = (onUndo?: () => void) => (onUndo ? { action: { label: 'Undo', onClick: onUndo } } : {})

export const notify = {
  queued: () => toast.info(QUEUED_TITLE, { id: ID.offline, description: QUEUED_BODY }),

  stopwatchStarted: (queued = false) =>
    queued ? notify.queued() : toast.success('Stopwatch started', { id: ID.stopwatch }),
  stopwatchPaused: (queued = false) =>
    queued ? notify.queued() : toast.info('Stopwatch paused', { id: ID.stopwatch }),
  stopwatchResumed: (queued = false) =>
    queued ? notify.queued() : toast.success('Stopwatch resumed', { id: ID.stopwatch }),
  /** `outcome` is the server's word for what happened to the time. */
  stopwatchStopped: (opts: { saved: boolean; outcome?: string; seconds: number; queued?: boolean }) => {
    if (opts.queued) return notify.queued()
    if (!opts.saved) return toast.info('Stopwatch discarded', { id: ID.stopwatch, description: 'Nothing was saved.' })
    if (opts.outcome === 'too_short')
      return toast.info('Under a minute, so not saved', {
        id: ID.stopwatch,
        description: 'Study at least a minute to log time.',
      })
    return toast.success(`Saved ${formatDuration(opts.seconds)} of study time`, { id: ID.stopwatch })
  },

  sessionAdded: (queued: boolean) => (queued ? notify.queued() : toast.success('Study time added')),
  sessionUpdated: () => toast.success('Session updated'),
  sessionDeleted: (seconds: number, onUndo?: () => void) =>
    toast.success(`Deleted ${formatDuration(seconds)} of study time`, { duration: 10_000, ...undo(onUndo) }),
  sessionSplit: (onUndo?: () => void) => toast.success('Session split in two', { duration: 10_000, ...undo(onUndo) }),
  sessionsMerged: (count: number, onUndo?: () => void) =>
    toast.success(`Merged ${count} sessions`, { duration: 10_000, ...undo(onUndo) }),
  undone: () => toast.success('Change undone'),

  goalsSaved: () => toast.success('Goals saved'),
  settingsSaved: () => toast.success('Settings saved'),
  settingsReset: () => toast.success('Settings reset to defaults'),

  exportStarted: (what: string) => toast.info(`Preparing ${what}`, { id: `tracker-export-${what}` }),
  exportFinished: (what: string) => toast.success(`${what} downloaded`, { id: `tracker-export-${what}` }),
  dataDeleted: () => toast.success('Tracker data deleted'),

  synced: (count: number) =>
    toast.success(count === 1 ? '1 change synced' : `${count} changes synced`, { id: ID.sync }),
  syncConflict: (count: number) =>
    toast.warning(count === 1 ? '1 change could not be applied' : `${count} changes could not be applied`, {
      id: ID.sync,
      description: 'The server rejected them, for example because they overlapped other study time. Check your log.',
    }),

  /** API and network failures. The message comes from the server envelope when there is one. */
  error: (error: unknown, fallback: string) => toastApiError(error, fallback),
}
