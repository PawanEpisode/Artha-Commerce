/** Shapes the R2 library, search and settings screens read beyond the document client (`document-types.ts`). */
import type { DocumentSummary, OcrLang, PageTone } from './document-types'
import type { NoteLink, TagRef } from './types'

export const COLOR_KEYS = ['y', 'g', 'b', 'p', 'o'] as const
export type ColorKey = (typeof COLOR_KEYS)[number]
export type ColorLegend = Record<ColorKey, string>
export type OcrDefault = 'ask' | 'always' | 'never'

/** `GET settings/` (R1 keys plus the R2 reader and OCR keys). */
export interface NotesSettings {
  color_legend: ColorLegend
  legend_schema: number
  default_color: ColorKey
  page_tone: PageTone
  finger_draws: boolean
  ocr_default: OcrDefault
  ocr_lang: OcrLang
  capabilities?: { recall: boolean; ocr_hindi: boolean; ai_ocr: boolean; ai_summary?: boolean }
}
export type NotesSettingsPatch = Partial<Omit<NotesSettings, 'legend_schema' | 'capabilities'>>

export type MarkKind = 'highlight' | 'underline' | 'ink' | 'textbox' | 'sticky' | 'bookmark' | 'area'

/** An aggregate row of a mark: the text kinds only (highlight, underline, area, sticky, textbox). */
export interface HighlightRow {
  type: 'highlight'
  id: string
  document_id: string
  page: number
  kind: MarkKind
  color: string | null
  comment: string
  quote_exact: string | null
  link: NoteLink
  tags: TagRef[]
  recall_card_id: string | null
  updated_at: string
}

export type DocumentRow = DocumentSummary & { type: 'document' }

export interface PdfSearchHit {
  type: 'pdf'
  document_id: string
  document_title: string
  page: number
  snippet: string
  rank: number
  link: NoteLink
}

export interface MarkSearchHit {
  type: 'highlight'
  annotation_id: string
  document_id: string
  document_title: string
  page: number
  snippet: string
  color: string | null
  rank: number
  link: NoteLink
}

export type NotSearchableReason = 'locked' | 'scanned' | 'pending'
export interface SearchMeta {
  indexing_documents: number
  not_searchable: Array<{ document_id: string; reason: NotSearchableReason }>
}
