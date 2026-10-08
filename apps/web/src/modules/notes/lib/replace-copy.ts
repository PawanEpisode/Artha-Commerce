import type { DocumentSummary } from './document-types'
import type { AttentionItem } from './replace-types'

type ReplaceDoc = Pick<DocumentSummary, 'reanchor_status' | 'reanchor'>

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/** The one line under a new edition: where its marks are. `null` when the document is not a replacement. */
export function replaceStatusText(doc: ReplaceDoc): string | null {
  const stats = doc.reanchor
  switch (doc.reanchor_status) {
    case 'waiting':
      return 'Your marks will move here as soon as this file is checked.'
    case 'running':
      return 'Moving your marks to this edition…'
    case 'failed':
      return 'We could not move your marks. They are still on the old edition.'
    case 'done': {
      if (!stats) return null
      const placed = stats.attached + stats.moved
      if (stats.total === 0) return 'The old edition had no marks to move.'
      const base = `${plural(placed, 'mark')} moved to this edition.`
      return stats.needs_attention > 0 ? `${base} ${plural(stats.needs_attention, 'mark')} need your attention.` : base
    }
    default:
      return null
  }
}

export const isReplaceActive = (doc: ReplaceDoc) =>
  doc.reanchor_status === 'waiting' || doc.reanchor_status === 'running'

/** Why a mark was not placed, in the student's words. */
export function reasonText(reason: string): string {
  switch (reason) {
    case 'not_found':
      return 'These words are not in the new edition.'
    case 'low_score':
      return 'The words changed too much to be sure.'
    case 'page_changed':
      return 'The page was rewritten.'
    case 'no_page':
      return 'The new edition has no such page.'
    case 'cannot_compare':
      return 'We could not compare this page.'
    default:
      return 'We could not place this mark.'
  }
}

const KIND: Record<string, string> = {
  highlight: 'Highlight',
  underline: 'Underline',
  area: 'Box',
  sticky: 'Sticky note',
  textbox: 'Text box',
  bookmark: 'Bookmark',
  ink: 'Drawing',
}

export const kindText = (kind: string) => KIND[kind] ?? 'Mark'

export const canSaveAsNote = (item: Pick<AttentionItem, 'quote' | 'comment'>) =>
  Boolean(item.quote.trim() || item.comment.trim())

export const openCount = (items: readonly AttentionItem[]) => items.filter((i) => i.status === 'open').length

export const resolvedText = (status: AttentionItem['status']): string =>
  status === 'kept' ? 'Kept on the new edition' : status === 'noted' ? 'Saved as a note' : 'Dismissed'
