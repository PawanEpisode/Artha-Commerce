import { type OutlineNode, rangesFromOutline, validateRanges } from './chapter-inheritance'
import type { PageRange, RangeInput } from './document-types'
import { isRangesOverlap } from './errors'

/** One row of the page-range editor. Page numbers are text while typing; `chapterId` is empty until one is chosen. */
export interface RangeRow {
  key: string
  from: string
  to: string
  chapterId: string
  /** "GST: Input tax credit", shown on the row. */
  chapterLabel: string
  topicId: string | null
  source: PageRange['source']
}

let counter = 0
export const newRowKey = () => `row-${++counter}`

export const rowsFromRanges = (ranges: readonly PageRange[]): RangeRow[] =>
  [...ranges]
    .sort((a, b) => a.page_from - b.page_from)
    .map((r) => ({
      key: r.id,
      from: String(r.page_from),
      to: String(r.page_to),
      chapterId: r.chapter_id,
      chapterLabel: [r.subject_name, r.chapter_name].filter(Boolean).join(' › '),
      topicId: r.topic_id,
      source: r.source,
    }))

export const emptyRow = (from = ''): RangeRow => ({
  key: newRowKey(),
  from,
  to: '',
  chapterId: '',
  chapterLabel: '',
  topicId: null,
  source: 'user',
})

/** A whole number of at least 1, or null for anything else (empty, "3a", "2.5"). */
export const parsePage = (text: string): number | null =>
  /^\d{1,6}$/.test(text.trim()) && Number(text) >= 1 ? Number(text) : null

/** The next row starts after the last one ends, so adding a row never begins with an overlap. */
export function nextRowStart(rows: readonly RangeRow[], pageCount: number | null): string {
  const ends = rows.map((r) => parsePage(r.to)).filter((n): n is number => n !== null)
  const next = ends.length > 0 ? Math.max(...ends) + 1 : 1
  return pageCount && next > pageCount ? '' : String(next)
}

export type RowProblems = Record<string, string>

/**
 * What is wrong with each row, by key (empty means the set can be saved). Uses `validateRanges` (the twin of the server
 * rule) for numbers and overlap, so the editor and the API agree; the 409 `ranges_overlap` is mapped back to the same rows.
 */
export function validateRows(rows: readonly RangeRow[], pageCount: number | null): RowProblems {
  const problems: RowProblems = {}
  const checked: Array<{ row: RangeRow; page_from: number; page_to: number }> = []
  for (const row of rows) {
    const page_from = parsePage(row.from)
    const page_to = parsePage(row.to)
    if (page_from === null || page_to === null) problems[row.key] = 'Enter whole page numbers, from 1.'
    else if (page_from > page_to) problems[row.key] = 'The first page must not be after the last page.'
    else if (pageCount !== null && page_to > pageCount) problems[row.key] = `This PDF has ${pageCount} pages.`
    else if (!row.chapterId) problems[row.key] = 'Choose a chapter for these pages.'
    else checked.push({ row, page_from, page_to })
  }
  const overlap = validateRanges(checked)
  if (overlap && overlap.code === 'overlap') {
    const a = checked[overlap.a]
    const b = checked[overlap.b]
    if (a && b) {
      problems[a.row.key] ??= `Overlaps pages ${b.page_from} to ${b.page_to}.`
      problems[b.row.key] ??= `Overlaps pages ${a.page_from} to ${a.page_to}.`
    }
  }
  return problems
}

/** What `PUT chapters/` is sent: rows in page order, with the order the server's `{a, b}` indexes refer to. */
export function toRangeInputs(rows: readonly RangeRow[]): { inputs: RangeInput[]; order: RangeRow[] } {
  const order = [...rows].sort((x, y) => (parsePage(x.from) ?? 0) - (parsePage(y.from) ?? 0))
  return {
    order,
    inputs: order.map((r) => ({
      page_from: parsePage(r.from) ?? 0,
      page_to: parsePage(r.to) ?? 0,
      chapter_id: r.chapterId,
      topic_id: r.topicId,
      source: r.source,
    })),
  }
}

/** The rows a 409 `ranges_overlap` points at (`details {a, b}` index the ranges that were sent). */
export function overlapRows(error: unknown, order: readonly RangeRow[]): RowProblems {
  if (!isRangesOverlap(error)) return {}
  const details = ((error as { body?: { error?: { details?: { a?: number; b?: number } } } }).body?.error?.details ??
    {}) as {
    a?: number
    b?: number
  }
  const a = typeof details.a === 'number' ? order[details.a] : undefined
  const b = typeof details.b === 'number' ? order[details.b] : undefined
  const out: RowProblems = {}
  if (a) out[a.key] = b ? `Overlaps pages ${b.from} to ${b.to}.` : 'Overlaps another range.'
  if (b) out[b.key] = a ? `Overlaps pages ${a.from} to ${a.to}.` : 'Overlaps another range.'
  return out
}

/** Rows from the PDF's own outline: one per top-level entry, chapters still to be chosen (or guessed by the server). */
export function rowsFromOutlineSuggestions(
  outline: readonly OutlineNode[],
  pageCount: number,
): Array<RangeRow & { title: string }> {
  return rangesFromOutline(outline, pageCount).map((s) => ({
    ...emptyRow(String(s.page_from)),
    to: String(s.page_to),
    source: 'outline' as const,
    title: s.title,
  }))
}

/** Adds suggested rows without touching the student's own: a suggestion that overlaps an existing row is skipped. */
export function mergeSuggestions(rows: readonly RangeRow[], suggestions: readonly RangeRow[]): RangeRow[] {
  const merged = [...rows]
  for (const suggestion of suggestions) {
    const candidate = [...merged, suggestion]
    const checked = candidate.flatMap((r) => {
      const page_from = parsePage(r.from)
      const page_to = parsePage(r.to)
      return page_from !== null && page_to !== null ? [{ page_from, page_to }] : []
    })
    if (validateRanges(checked)?.code !== 'overlap') merged.push(suggestion)
  }
  return merged.sort((a, b) => (parsePage(a.from) ?? 0) - (parsePage(b.from) ?? 0))
}

/** Are the rows the same as the saved ranges (nothing to save)? */
export function sameAsSaved(rows: readonly RangeRow[], saved: readonly PageRange[]): boolean {
  const a = toRangeInputs(rows).inputs
  const b = [...saved].sort((x, y) => x.page_from - y.page_from)
  return (
    a.length === b.length &&
    a.every((r, i) => {
      const s = b[i]
      return (
        s &&
        r.page_from === s.page_from &&
        r.page_to === s.page_to &&
        r.chapter_id === s.chapter_id &&
        (r.topic_id ?? null) === (s.topic_id ?? null)
      )
    })
  )
}
