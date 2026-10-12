import { ALL_CHAPTERS } from '~/modules/coverage'

import {
  buildSelection,
  isSubjectLevel,
  linkFields,
  type LinkSelection,
  type PickerOption,
  type PickerState,
  sameLink,
} from './chapter-link'
import type { DocumentDetail, DocumentPatch, PageRange, RangeInput, SourceKind } from './document-types'
import { filledRows, type RangeRow, rowsFromRanges, sameAsSaved, toRangeInputs, validateRows } from './page-ranges'

/** Everything the upload and edit dialogs collect about a PDF, kept in one place so both flows share it. */
export interface DocumentDraft {
  title: string
  source_kind: SourceKind
  edition_label: string
  tag_ids: string[]
  /** Subject, chapter (or `ALL_CHAPTERS`) and topic. All empty means Unfiled. */
  filing: PickerState
  rows: RangeRow[]
}

export type FormStepId = 'details' | 'filing' | 'ranges'

export const EMPTY_FILING: PickerState = { subjectId: '', chapterId: '', topicId: '' }

export const TITLE_MAX = 200
export const EDITION_MAX = 40

/** The twin of the server's `title_from_filename`: no folders, no ".pdf", underscores as spaces. */
export function titleFromFilename(filename: string): string {
  const base = filename.replace(/\\/g, '/').split('/').pop()?.trim() ?? ''
  const stem = base.replace(/\.[^./]*$/, '')
  return stem.replace(/_/g, ' ').split(/\s+/).filter(Boolean).join(' ').slice(0, TITLE_MAX) || 'Untitled PDF'
}

export const draftFromFile = (filename: string): DocumentDraft => ({
  title: titleFromFilename(filename),
  source_kind: 'other',
  edition_label: '',
  tag_ids: [],
  filing: EMPTY_FILING,
  rows: [],
})

/**
 * The filing a document has now, as picker choices. The subject is found by its stable key in the student's list (ids change
 * with a syllabus scheme), then by the stored id.
 */
export function filingFromDocument(doc: Pick<DocumentDetail, 'link'>, subjects: readonly PickerOption[]): PickerState {
  const { link } = doc
  if (!link.subject_key) return EMPTY_FILING
  const subjectId = subjects.find((s) => s.key === link.subject_key)?.id ?? link.subject_id ?? ''
  if (isSubjectLevel(link)) return { subjectId, chapterId: ALL_CHAPTERS, topicId: '' }
  return { subjectId, chapterId: link.chapter_id ?? '', topicId: link.topic_id ?? '' }
}

export const draftFromDocument = (doc: DocumentDetail, subjects: readonly PickerOption[]): DocumentDraft => ({
  title: doc.title,
  source_kind: doc.source_kind,
  edition_label: doc.edition_label ?? '',
  tag_ids: doc.tags.map((t) => t.id),
  filing: filingFromDocument(doc, subjects),
  rows: rowsFromRanges(doc.ranges),
})

/** The subject is chosen but not what part of it: say so rather than file it somewhere the student did not mean. */
export const filingProblem = (filing: PickerState): string | null =>
  filing.subjectId !== '' && filing.chapterId === '' ? 'Choose a chapter, or All chapters for the whole subject.' : null

export const titleProblem = (title: string): string | null => (title.trim() === '' ? 'Give the PDF a title.' : null)

/** The first step with something to fix, or null when the draft can be saved. */
export function firstInvalidStep(draft: DocumentDraft, pageCount: number | null): FormStepId | null {
  if (titleProblem(draft.title)) return 'details'
  if (filingProblem(draft.filing)) return 'filing'
  if (Object.keys(validateRows(filledRows(draft.rows), pageCount)).length > 0) return 'ranges'
  return null
}

/** The picker's choice as a finished selection (null for Unfiled), or undefined while the lists it needs are not loaded. */
export function selectionOfDraft(
  levelId: string | undefined,
  filing: PickerState,
  subjects: PickerOption[],
  chapters: PickerOption[],
  topics: PickerOption[],
): LinkSelection | null | undefined {
  if (filing.subjectId === '') return null
  if (levelId === undefined) return undefined
  return buildSelection(levelId, filing, subjects, chapters, topics) ?? undefined
}

const sameIds = (a: readonly string[], b: readonly string[]) => [...a].sort().join(',') === [...b].sort().join(',')

/**
 * What changed in an existing document, as the PATCH body (only changed fields, with `base_rev`), or null for no change.
 * `selection` is `undefined` while the filing lists are loading: the filing is then left alone.
 */
export function documentPatch(
  doc: DocumentDetail,
  draft: DocumentDraft,
  selection: LinkSelection | null | undefined,
): DocumentPatch | null {
  const patch: DocumentPatch = { base_rev: doc.rev }
  if (draft.title.trim() !== doc.title) patch.title = draft.title.trim()
  if (draft.source_kind !== doc.source_kind) patch.source_kind = draft.source_kind
  const edition = draft.edition_label.trim() || null
  if (edition !== doc.edition_label) patch.edition_label = edition
  if (
    !sameIds(
      draft.tag_ids,
      doc.tags.map((t) => t.id),
    )
  )
    patch.tag_ids = draft.tag_ids
  if (selection !== undefined && !sameLink(selection, doc.link)) Object.assign(patch, linkFields(selection))
  return Object.keys(patch).length === 1 ? null : patch
}

/** What an upload sends beyond the file: only what differs from the defaults the server would use. */
export interface UploadDetails {
  title?: string
  edition_label?: string
  tag_ids?: string[]
}

export function uploadDetails(draft: DocumentDraft, filename: string): UploadDetails {
  const out: UploadDetails = {}
  const title = draft.title.trim()
  if (title !== '' && title !== titleFromFilename(filename)) out.title = title
  const edition = draft.edition_label.trim()
  if (edition !== '') out.edition_label = edition
  if (draft.tag_ids.length > 0) out.tag_ids = draft.tag_ids
  return out
}

/** The page ranges of a draft as the API takes them (blank rows left out, page order). */
export const rangeInputsOf = (draft: DocumentDraft): RangeInput[] => toRangeInputs(filledRows(draft.rows)).inputs

/** Are the draft's ranges the same as the saved ones (nothing to write)? */
export const sameRanges = (draft: DocumentDraft, saved: readonly PageRange[]): boolean =>
  sameAsSaved(filledRows(draft.rows), saved)
