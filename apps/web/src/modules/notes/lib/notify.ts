import { toast, toastApiError } from '@artha/design-system'

import { pluralize } from './format'

/** The one place that words every notes outcome. Toasts say what happened; field problems stay inline. */
const ID = { offline: 'notes-offline', sync: 'notes-sync', trash: 'notes-trash', clip: 'notes-clip' } as const

/** How long "Undo" stays on a trashed note (FR-F03-36). */
export const UNDO_MS = 10_000

export const notify = {
  queued: () =>
    toast.info('Saved on this device', { id: ID.offline, description: 'It will sync when you are back online.' }),

  noteCreated: () => toast.success('Note saved'),

  trashed: (onUndo: () => void) =>
    toast.info('Moved to Trash', {
      id: ID.trash,
      description: 'Kept for 30 days.',
      duration: UNDO_MS,
      action: { label: 'Undo', onClick: onUndo },
    }),
  restored: () => toast.success('Note restored'),
  versionRestored: (rev: number) =>
    toast.success(`Restored version ${rev}`, { description: 'It is now the latest version.' }),

  overwritten: (fields: string[]) =>
    toast.info('Another device had a newer change', {
      id: 'notes-overwritten',
      description: `Your ${fields.map((f) => (f === 'chapter_id' ? 'chapter' : f === 'topic_id' ? 'topic' : f)).join(' and ')} replaced it. You can change it back.`,
    }),
  restoredByEdit: () => toast.info('Note restored from Trash', { description: 'Editing it brought it back.' }),

  filed: (where: string) => toast.success(`Filed under ${where}`),
  unfiled: () => toast.info('Moved to Unfiled'),
  pinned: (on: boolean) => toast.success(on ? 'Pinned to the top' : 'Unpinned'),

  clipSaved: (onOpen?: () => void) =>
    toast.success('Saved to notes', { id: ID.clip, ...(onOpen ? { action: { label: 'Open', onClick: onOpen } } : {}) }),
  clipQueued: () => notify.queued(),

  synced: (count: number) => toast.success(`${pluralize(count, 'note change')} synced`, { id: ID.sync }),
  syncDropped: (count: number) =>
    toast.warning(`${pluralize(count, 'change')} could not be saved`, {
      id: ID.sync,
      description: 'The server refused it. Open the note to check your text.',
    }),
  conflictResolved: () => toast.success('Conflict settled', { description: 'Nothing was lost.' }),
  autoMerged: () => toast.info('Merged with changes from another device'),
  recovered: () => toast.info('Recovered draft', { description: 'Your text was restored from this device.' }),

  quotaFull: (kind: string) =>
    toast.warning(kind === 'tags' ? 'Tag limit reached' : 'Notes storage is full', {
      description: 'Delete something you no longer need, or export your notes first.',
    }),
  exportStarted: () => toast.info('Preparing your export'),
  allDeleted: () => toast.success('All your notes were deleted'),

  error: (error: unknown, fallback: string) => toastApiError(error, fallback),
}
