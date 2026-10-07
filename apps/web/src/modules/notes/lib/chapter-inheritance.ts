/**
 * Which chapter a mark on a PDF page belongs to (FR-F03-30), the TypeScript twin of
 * `apps/api/modules/notes/domain/chapter_inheritance.py` (shared `inheritance_cases.json`). Explicit beats the page range,
 * which beats the document default. The chapter reference is opaque (an id): this file never looks inside it.
 */

export type ChapterSource = 'explicit' | 'range' | 'document' | 'none'

export interface PageRange<C = string> {
  page_from: number
  page_to: number
  chapter: C | null
}

export interface RangeProblem {
  code: 'invalid_range' | 'overlap'
  /** Indexes into the ranges that were checked. */
  a: number
  b: number
}

export interface OutlineNode {
  title: string
  page: number | null
  children?: OutlineNode[]
}

export interface SuggestedRange {
  page_from: number
  page_to: number
  title: string
}

/** The chapter and where it came from. Ranges are inclusive; the first match wins. */
export function effectiveLink<C>(
  page: number,
  explicitChapter: C | null | undefined,
  ranges: readonly PageRange<C>[],
  documentDefault: C | null | undefined,
): { chapter: C | null; source: ChapterSource } {
  if (explicitChapter !== null && explicitChapter !== undefined) return { chapter: explicitChapter, source: 'explicit' }
  for (const r of ranges) {
    if (r.page_from <= page && page <= r.page_to && r.chapter !== null && r.chapter !== undefined) {
      return { chapter: r.chapter, source: 'range' }
    }
  }
  if (documentDefault !== null && documentDefault !== undefined) return { chapter: documentDefault, source: 'document' }
  return { chapter: null, source: 'none' }
}

/** Null when the ranges are usable, else the first problem (see the Python twin for the exact rule). */
export function validateRanges(ranges: readonly Pick<PageRange, 'page_from' | 'page_to'>[]): RangeProblem | null {
  for (const [i, r] of ranges.entries()) {
    if (!(
      Number.isInteger(r.page_from) &&
      Number.isInteger(r.page_to) &&
      r.page_from >= 1 &&
      r.page_from <= r.page_to
    )) {
      return { code: 'invalid_range', a: i, b: i }
    }
  }
  const order = ranges
    .map((_, i) => i)
    .sort(
      (x, y) =>
        (ranges[x]?.page_from ?? 0) - (ranges[y]?.page_from ?? 0) ||
        (ranges[x]?.page_to ?? 0) - (ranges[y]?.page_to ?? 0) ||
        x - y,
    )
  let furthest: number | null = null
  for (const k of order) {
    const current = ranges[k]
    const reach = furthest === null ? null : ranges[furthest]
    if (current && reach && current.page_from <= reach.page_to) return { code: 'overlap', a: furthest as number, b: k }
    if (current && (reach === null || current.page_to > reach.page_to)) furthest = k
  }
  return null
}

/** One suggested range per top-level outline entry, to the page before the next one (the last to `pageCount`). */
export function rangesFromOutline(outline: readonly OutlineNode[], pageCount: number): SuggestedRange[] {
  const usable = outline
    .map((node, i) => ({ page: node.page, i, title: node.title ?? '' }))
    .filter(
      (e): e is { page: number; i: number; title: string } =>
        Number.isInteger(e.page) && (e.page as number) >= 1 && (e.page as number) <= pageCount,
    )
    .sort((x, y) => x.page - y.page || x.i - y.i)
  const entries: { page: number; title: string }[] = []
  for (const e of usable) if (entries.length === 0 || entries[entries.length - 1]?.page !== e.page) entries.push(e)
  return entries.map((e, k) => ({
    page_from: e.page,
    page_to: k + 1 < entries.length ? (entries[k + 1]?.page as number) - 1 : pageCount,
    title: e.title,
  }))
}
