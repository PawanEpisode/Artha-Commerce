import type { ReanchorStats, ReanchorStatus } from './document-types'

export type AttentionStatus = 'open' | 'kept' | 'noted' | 'dismissed'
export type AttentionAction = 'keep' | 'note' | 'dismiss'
export type AttentionReason =
  'not_found' | 'low_score' | 'page_changed' | 'cannot_compare' | 'no_page' | 'invalid' | string

/** A mark of the old edition that could not be placed on the new one with confidence. */
export interface AttentionItem {
  id: string
  source_annotation_id: string
  kind: string
  /** The page in the OLD edition. */
  page: number
  color: string
  quote: string
  comment: string
  reason: AttentionReason
  status: AttentionStatus
  new_annotation_id: string | null
  result_note_id: string | null
  resolved_at: string | null
}

export interface Attention {
  document_id: string
  replaces_document_id: string | null
  status: ReanchorStatus
  stats: ReanchorStats | null
  items: AttentionItem[]
}
