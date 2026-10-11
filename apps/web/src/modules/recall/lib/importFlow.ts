import { ApiError } from '~/lib/api'

import { cardFailure } from './cardErrors'
import type { ImportResult, ImportRow } from './schemas'

/** The API takes at most this many rows in one import (the ERD names no limit, so it is the same 200 as a bulk change). */
export const IMPORT_ROW_LIMIT = 200
/** The biggest file the panel reads (the API takes 400,000 characters of text). */
export const IMPORT_FILE_MAX_BYTES = 400_000

export const IMPORT_EXAMPLE_PLAIN = 'Time limit to claim ITC? :: 30 November of the next year'
export const IMPORT_EXAMPLE_COLUMNS =
  'kind,front,back,chapter\npointer,Time limit to claim ITC?,30 November of the next year,'

const rows = (n: number): string => `${n} ${n === 1 ? 'row' : 'rows'}`

/** The line under the preview table: what the import will do. */
export function previewSentence(r: ImportResult): string {
  if (r.total === 0) return 'There are no rows to import.'
  if (r.valid === 0) return `None of the ${rows(r.total)} can be imported yet. Fix them above and check again.`
  const skipped = r.invalid > 0 ? `, and ${rows(r.invalid)} with a problem will be skipped` : ''
  return `${rows(r.valid)} ${r.valid === 1 ? 'is' : 'are'} ready${skipped}.`
}

/** The heading of the result after the real import. */
export function doneHeading(r: ImportResult): string {
  if (r.created > 0) return `${rows(r.created)} imported`
  if (r.existing > 0) return 'These cards were already imported'
  return 'No rows were imported'
}

export function doneDetail(r: ImportResult): string {
  const parts: string[] = []
  if (r.invalid > 0) parts.push(`${rows(r.invalid)} had a problem and ${r.invalid === 1 ? 'was' : 'were'} skipped`)
  if (r.existing > 0) parts.push(`${rows(r.existing)} ${r.existing === 1 ? 'was' : 'were'} already there`)
  return parts.length > 0 ? `${parts.join('. ')}.` : 'They will show up in your reviews soon.'
}

/** The text of a row's result cell: "Ready", "Made", or the problems in plain words. */
export function rowResult(row: ImportRow): { tone: 'ok' | 'error'; lines: string[] } {
  switch (row.status) {
    case 'ok':
      return { tone: 'ok', lines: ['Ready'] }
    case 'created':
      return { tone: 'ok', lines: ['Made'] }
    case 'existing':
      return { tone: 'ok', lines: ['Already imported'] }
    default:
      return {
        tone: 'error',
        lines: row.issues.length > 0 ? row.issues.map((i) => i.message) : ['This row cannot be imported.'],
      }
  }
}

/** Whether the real import may start: the rows were checked, at least one is valid and they fit her plan. */
export const canImport = (r: ImportResult | null, textChanged: boolean): boolean =>
  r !== null && r.dry_run && !textChanged && r.valid > 0 && r.quota.fits

/** One sentence for a failed preview or import. Nothing was added in any of these cases. */
export function importFailure(error: unknown): string {
  if (error instanceof ApiError && error.code === 'import_too_large')
    return `You can import at most ${IMPORT_ROW_LIMIT} rows at a time. Split your list and import it in parts.`
  if (error instanceof ApiError && error.code === 'unknown_chapter') return 'That chapter is not in your syllabus.'
  const f = cardFailure(error)
  if (f.kind === 'quota') return `${f.message} Nothing was added.`
  if (f.kind === 'network') return 'The connection dropped. Nothing was added, so you can try again.'
  if (f.kind === 'throttled') return 'Too many requests at once. Wait a moment and try again.'
  return 'We could not import these rows. Nothing was added. Please try again.'
}
