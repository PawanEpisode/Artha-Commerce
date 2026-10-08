/** Shapes of the R2 annotation endpoints (`/api/v1/notes/annotations/...`). Mirrors the R2 section of docs/F-03-API-CONTRACT.md. */
import type { Geometry, MarkKind } from './geometry'
import type { NoteLink, TagRef } from './types'

export type { Geometry, MarkKind }

export const MARKUP_COLORS = ['y', 'g', 'b', 'p', 'o'] as const
export const INK_COLORS = ['i1', 'i2', 'i3', 'i4', 'i5'] as const
export type MarkupColor = (typeof MARKUP_COLORS)[number]
export type InkColor = (typeof INK_COLORS)[number]
export type ColorKey = MarkupColor | InkColor

export type ChapterSource = 'explicit' | 'range' | 'document' | 'none'
export type AnchorEngine = 'pdfjs' | 'ocr'
export type Resolution = 'mine' | 'theirs' | 'both'

export interface Annotation {
  id: string
  document_id: string
  page: number
  kind: MarkKind
  geometry: Geometry
  color: ColorKey | null
  comment: string
  quote_exact: string | null
  quote_prefix: string | null
  quote_suffix: string | null
  text_start: number | null
  text_end: number | null
  anchor_engine: AnchorEngine | null
  link: NoteLink
  chapter_source: ChapterSource
  tags: TagRef[]
  recall_card_id: string | null
  rev: number
  seq: number
  device_id: string | null
  created_at: string
  updated_at: string
  deleted_at: string | null
}

/**
 * A mark as this device holds it. `local_only` is set from the moment it is made here until the server has answered
 * its create (the id is client generated, so it is the same row afterwards).
 */
export interface MarkRecord extends Annotation {
  local_only?: true
}

/** Fields of a mark the student can set; what a create sends and what an edit may change (`kind` never changes). */
export interface MarkFields {
  page: number
  geometry: Geometry
  color: ColorKey | null
  comment: string
  quote_exact: string | null
  quote_prefix: string | null
  quote_suffix: string | null
  text_start: number | null
  text_end: number | null
  anchor_engine: AnchorEngine | null
  chapter_id: string | null
  topic_id: string | null
  tag_ids: string[]
}

/** What the screen hands over to make a mark: everything but the identity, which the hook gives it. */
export type MarkDraft = Pick<MarkFields, 'page' | 'geometry'> &
  Partial<Omit<MarkFields, 'page' | 'geometry'>> & { kind: MarkKind }

export type MarkPatch = Partial<MarkFields>

/** `marks` in every write response: the plan's cap per document and the 95% flag. */
export interface MarksInfo {
  count: number
  limit: number
  near_limit: boolean
}

export interface DeltaPage {
  items: Annotation[]
  change_seq: number
  next_since_seq: number
  has_more: boolean
}

export interface WriteResponse {
  annotation: Annotation
  merged?: boolean
  restored?: boolean
  overwritten?: string[]
  edit_wins?: boolean
  change_seq: number
  marks?: MarksInfo
}

export interface BatchOpBody {
  op: 'upsert' | 'delete' | 'restore'
  id: string
  document_id?: string
  base_rev?: number
  base?: Record<string, unknown>
  resolution?: Resolution
  [field: string]: unknown
}

export interface BatchError {
  code: string
  message: string
  details?: unknown
}

export type BatchResultItem =
  | {
      id: string
      status: 'ok'
      annotation: Annotation
      merged?: boolean
      restored?: boolean
      overwritten?: string[]
      edit_wins?: boolean
    }
  | { id: string; status: 'conflict' | 'rejected'; error: BatchError }

export interface BatchResponse {
  results: BatchResultItem[]
  change_seq: number
  marks?: MarksInfo
}

/** 409 `annotation_conflict` details: the student's version, the stored one and where it came from. */
export interface AnnotationConflictDetail {
  mine: Partial<Annotation> & { comment?: string }
  theirs: Annotation
  device_label: string | null
  theirs_updated_at: string
}

export type CardKind = 'formula' | 'rule' | 'definition' | 'example' | 'doubt' | 'fact'

export type { NotesSettings } from './library-types'
