/** Shapes of the R2 document endpoints (`/api/v1/notes/documents/...`). Mirrors the R2 section of docs/F-03-API-CONTRACT.md. */
import type { NoteLink, Page, TagRef } from './types'

export type DocumentStatus =
  'reserved' | 'scanning' | 'inspecting' | 'ready' | 'needs_password' | 'rejected' | 'expired' | 'failed'
export type DocumentStatusReason =
  'type_mismatch' | 'malware' | 'pdf_corrupt' | 'too_many_pages' | 'too_large' | 'decode_failed' | 'policy'
export type SourceKind = 'institute_material' | 'coaching' | 'own_notes' | 'handwritten' | 'other'
export type TextStatus = 'pending' | 'running' | 'done' | 'failed' | 'locked' | 'skipped'
export type OcrStatus = 'none' | 'pending' | 'running' | 'partial' | 'done' | 'failed'
export type OcrMode = 'none' | 'tesseract' | 'ai'
export type OcrLang = 'eng' | 'eng+hin'
export type PageTone = 'original' | 'paper' | 'night'
/** `fit` or a percent as text (`"120"`): CSS pixels per PDF point times 100. */
export type StoredZoom = string

export type UnlockStatus = 'none' | 'waiting' | 'running' | 'done' | 'failed'
export type UnlockReason = 'wrong_password' | 'restricted' | 'unreadable' | 'expired'
export type ReanchorStatus = 'none' | 'waiting' | 'running' | 'done' | 'failed'
export interface ReanchorStats {
  total: number
  attached: number
  moved: number
  needs_attention: number
  ranges_copied: number
}

export interface DocumentSummary {
  id: string
  origin: 'upload' | 'platform'
  title: string
  original_filename: string
  source_kind: SourceKind
  edition_label: string | null
  /** Set on a newer edition made with "Replace edition": the old document its marks came from. */
  replaces_document_id: string | null
  reanchor_status: ReanchorStatus
  reanchor: ReanchorStats | null
  /** Unlock for search: reading the text of a locked PDF with the student's password. */
  unlock_status: UnlockStatus
  unlock_reason: UnlockReason | null
  status: DocumentStatus
  status_reason: DocumentStatusReason | null
  bytes: number
  page_count: number | null
  is_scanned: boolean | null
  is_encrypted: boolean
  can_copy: boolean | null
  can_modify: boolean | null
  text_status: TextStatus
  text_pages_done: number
  ocr_status: OcrStatus
  ocr_pages_done: number
  ocr_pages_total: number
  ocr_mode: OcrMode
  ocr_lang: OcrLang
  last_page: number
  last_zoom: StoredZoom
  page_tone: PageTone | null
  last_opened_at: string | null
  marks_count: number
  /** Signed, valid one hour. */
  cover_url: string | null
  duplicate_of: string | null
  link: NoteLink
  tags: TagRef[]
  rev: number
  created_at: string
  updated_at: string
  deleted_at: string | null
  purge_after: string | null
}

export interface PageSize {
  /** Points, the page as displayed (intrinsic rotation applied). */
  w: number
  h: number
}

export interface OutlineNode {
  title: string
  /** 1-based page, 0 or absent when the entry has no destination inside the file. */
  page: number
  children: OutlineNode[]
}

export interface PageRange {
  id: string
  page_from: number
  page_to: number
  source: 'user' | 'outline' | 'ai'
  chapter_id: string
  chapter_key: string
  subject_key: string
  subject_name: string
  chapter_name: string
  topic_id: string | null
  topic_key: string | null
  topic_name: string | null
}

export interface DocumentDetail extends DocumentSummary {
  client_id: string | null
  can_open: boolean
  /** Signed, valid four hours; present when the file is clean and the status is inspecting, ready or needs_password. */
  file_url: string | null
  file_url_expires_at: string | null
  page_meta: PageSize[] | null
  outline: OutlineNode[] | null
  has_javascript: boolean
  change_seq: number
  ranges: PageRange[]
}

/** The contract calls the detail shape `Document`; this name avoids the DOM global. */
export type { DocumentDetail as Document }

/** R3 resumable upload: a big file may be sent in parts (`documents/{id}/resumable/`). Absent for an ordinary single PUT. */
export interface ResumableHint {
  document_id: string
  part_size: number
  parts: number
}

export interface UploadTarget {
  url: string
  method: 'PUT'
  headers?: Record<string, string>
  expires_at: string
  resumable?: ResumableHint
}

export interface ReserveBody {
  client_id: string
  filename: string
  bytes: number
  mime: 'application/pdf'
  page_count_hint?: number
  source_kind?: SourceKind
  chapter_id?: string | null
  topic_id?: string | null
}

export interface ReserveResult {
  document: DocumentDetail
  /** Null on a replay once the file is past `reserved` (nothing left to send). */
  upload: UploadTarget | null
}

export interface DocumentListParams {
  subject?: string
  level?: string
  chapter?: string
  tag?: string
  status?: DocumentStatus
  source?: SourceKind
  q?: string
  trashed?: boolean
  sort?: 'recent' | 'title'
  cursor?: string
  limit?: number
}

export type DocumentPage = Page<DocumentSummary>

export interface DocumentPatch {
  base_rev?: number
  title?: string
  source_kind?: SourceKind
  edition_label?: string | null
  chapter_id?: string | null
  topic_id?: string | null
  tag_ids?: string[]
}

export interface RangeInput {
  page_from: number
  page_to: number
  chapter_id: string
  topic_id?: string | null
  source?: PageRange['source']
}

export interface ProgressBody {
  last_page: number
  last_zoom: StoredZoom
  page_tone?: PageTone | null
}

export interface ProgressResult {
  last_page: number
  last_zoom: StoredZoom
  page_tone: PageTone | null
  last_opened_at: string
}

export interface DocumentProcessing {
  status: DocumentStatus
  status_reason: DocumentStatusReason | null
  text_status: TextStatus
  text_pages_done: number
  ocr_status: OcrStatus
  ocr_pages_done: number
  ocr_pages_total: number
  page_count: number | null
  is_scanned: boolean | null
}

/** One OCR word: `[x, y, w, h, text]` in the normalised page frame (fractions of the page, four decimals). */
export type OcrWord = [number, number, number, number, string]

export interface PageText {
  page: number
  text: string
  source: 'native' | 'ocr' | 'ai'
  conf: number | null
  words: OcrWord[] | null
}

export interface PagesText {
  pages: PageText[]
  text_status: TextStatus
  ocr_status: OcrStatus
}

export interface DocumentSearchHit {
  page: number
  snippet: string
  rank: number
}

export interface DocumentSearchResult {
  items: DocumentSearchHit[]
  text_status: TextStatus
  ocr_status: OcrStatus
  indexed_pages: number
  page_count: number
}

export interface OcrRequest {
  mode: 'tesseract'
  lang?: OcrLang
  /** `"1-40,50"`; all pages when omitted. */
  pages?: string
}

export interface OcrStarted {
  status: OcrStatus
  ocr_pages_total: number
  charged_pages: number
  estimate_seconds: number
}

export type MarkExportKind = 'highlight' | 'underline' | 'ink' | 'textbox' | 'sticky' | 'area'

export interface ExportOptions {
  pages?: string
  include?: MarkExportKind[]
  colors?: string[]
  tags?: string[]
  appendix?: boolean
}

export interface ExportJob {
  id: string
  kind: 'pdf' | 'archive'
  document_id: string | null
  status: 'queued' | 'running' | 'done' | 'failed' | 'expired'
  progress: number
  page_count: number | null
  error_code: 'export_too_large' | 'restricted' | 'locked' | 'failed' | null
  download_url: string | null
  expires_at: string | null
  options: ExportOptions
  created_at: string
  /** `{suggested_pages}` when `error_code` is `export_too_large`. */
  details?: { suggested_pages?: string } | null
}

/** The statuses in which the server is still working on the file, so the reader polls `processing/`. */
export const PREPARING_STATUSES: ReadonlyArray<DocumentStatus> = ['reserved', 'scanning', 'inspecting']
export const isPreparing = (status: DocumentStatus) => PREPARING_STATUSES.includes(status)
export const isOcrRunning = (status: OcrStatus) => status === 'pending' || status === 'running'
