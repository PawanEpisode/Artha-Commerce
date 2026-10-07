import type { DocumentDetail, DocumentProcessing } from './document-types'
import { UNFILED_LINK } from './testing'

/** Test factories for R2 documents. Not imported by app code. */
export const DOC_ID = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'

export function makeDocument(overrides: Partial<DocumentDetail> = {}): DocumentDetail {
  const pages = overrides.page_count ?? 3
  return {
    id: DOC_ID,
    client_id: null,
    origin: 'upload',
    title: 'Taxation module',
    original_filename: 'taxation.pdf',
    source_kind: 'institute_material',
    edition_label: null,
    status: 'ready',
    status_reason: null,
    bytes: 2_000_000,
    page_count: pages,
    is_scanned: false,
    is_encrypted: false,
    can_copy: true,
    can_modify: true,
    can_open: true,
    text_status: 'done',
    text_pages_done: pages,
    ocr_status: 'none',
    ocr_pages_done: 0,
    ocr_pages_total: 0,
    ocr_mode: 'none',
    ocr_lang: 'eng',
    last_page: 1,
    last_zoom: 'fit',
    page_tone: null,
    last_opened_at: null,
    marks_count: 0,
    cover_url: null,
    duplicate_of: null,
    link: UNFILED_LINK,
    tags: [],
    rev: 1,
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-01T10:00:00Z',
    deleted_at: null,
    purge_after: null,
    file_url: 'https://storage.example/taxation.pdf?token=abc',
    file_url_expires_at: '2026-10-08T14:00:00Z',
    page_meta: Array.from({ length: pages }, () => ({ w: 595, h: 842 })),
    outline: null,
    has_javascript: false,
    change_seq: 0,
    ranges: [],
    ...overrides,
  }
}

export function makeProcessing(overrides: Partial<DocumentProcessing> = {}): DocumentProcessing {
  return {
    status: 'ready',
    status_reason: null,
    text_status: 'done',
    text_pages_done: 3,
    ocr_status: 'none',
    ocr_pages_done: 0,
    ocr_pages_total: 0,
    page_count: 3,
    is_scanned: false,
    ...overrides,
  }
}
