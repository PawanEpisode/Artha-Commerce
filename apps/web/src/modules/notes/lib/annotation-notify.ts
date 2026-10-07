import { toast } from '@artha/design-system'

import type { MarkKind } from './annotation-types'
import { KIND_LABEL } from './mark-label'
import { UNDO_MS } from './notify'

const ID = {
  overwritten: 'marks-overwritten',
  limit: 'marks-limit',
  dropped: 'marks-dropped',
  card: 'marks-card',
} as const

/** The one place that words every outcome of the annotation layer. Toasts say what happened, never what the mark says. */
export const markNotify = {
  deleted: (kind: MarkKind, onUndo: () => void) =>
    toast.info(`${KIND_LABEL[kind]} deleted`, {
      id: 'marks-deleted',
      duration: UNDO_MS,
      action: { label: 'Undo', onClick: onUndo },
    }),
  restored: (kind: MarkKind) => toast.success(`${KIND_LABEL[kind]} restored`),
  overwritten: (fields: string[]) =>
    toast.info('Another device had a newer change', {
      id: ID.overwritten,
      description: `Your ${fields.map((f) => (f === 'chapter_id' ? 'chapter' : f === 'topic_id' ? 'topic' : f)).join(' and ')} replaced it. You can change it back.`,
    }),
  editWins: () =>
    toast.info('Another device changed this mark', {
      id: ID.overwritten,
      description: 'It was kept instead of deleted.',
    }),
  limitReached: () =>
    toast.warning('This PDF has reached its limit of marks', {
      id: ID.limit,
      description: 'Delete some marks, starting with pages that hold a lot of ink.',
    }),
  dropped: (count: number) =>
    toast.warning(`${count === 1 ? 'A mark' : `${count} marks`} could not be saved`, {
      id: ID.dropped,
      description: 'The server refused it. The marks on the page match what is saved.',
    }),
  conflictResolved: () => toast.success('Conflict settled', { description: 'Nothing was lost.' }),
  cardCreated: () => toast.success('Card created', { id: ID.card }),
  cardNeedsConnection: () =>
    toast.info('Cards need a connection', { id: ID.card, description: 'Try again when you are online.' }),
  cardNoText: () => toast.info('There is no text to make a card from', { id: ID.card }),
  cardUnavailable: () => toast.info('Cards are not available yet', { id: ID.card }),
  cardFailed: () => toast.error('Could not make the card. Try again.', { id: ID.card }),
  highlightedHit: (page: number) => toast.success(`Highlighted on page ${page}`, { id: 'marks-hit' }),
  hitNotFound: () => toast.info('That result is not on the page any more', { id: 'marks-hit' }),
  noMarks: () => toast.info('No marks yet', { id: 'marks-hit' }),
  copied: () => toast.success('Copied'),
  copyFailed: () => toast.error('Could not copy the text.'),
}
