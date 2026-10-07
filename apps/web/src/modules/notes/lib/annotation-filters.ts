import type { Legend } from './annotation-legend'
import { colorName } from './annotation-legend'
import type { ColorKey, MarkKind, MarkRecord } from './annotation-types'
import { shortLinkLabel } from './chapter-link'
import { colorPhrase, describeMark, markHeading, markPreview } from './mark-label'
import type { TagRef } from './types'

export interface AnnotationFilters {
  color: ColorKey | ''
  /** A tag id. */
  tag: string
  kind: MarkKind | ''
  /** Marks made today (the student's day, local time). */
  today: boolean
}

export const NO_FILTERS: AnnotationFilters = { color: '', tag: '', kind: '', today: false }

export const activeFilterCount = (f: AnnotationFilters) =>
  (f.color ? 1 : 0) + (f.tag ? 1 : 0) + (f.kind ? 1 : 0) + (f.today ? 1 : 0)

const sameDay = (iso: string, now: Date) => {
  const d = new Date(iso)
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
}

export function applyFilters(marks: readonly MarkRecord[], filters: AnnotationFilters, now = new Date()): MarkRecord[] {
  return marks.filter(
    (m) =>
      (!filters.color || m.color === filters.color) &&
      (!filters.kind || m.kind === filters.kind) &&
      (!filters.tag || m.tags.some((t) => t.id === filters.tag)) &&
      (!filters.today || sameDay(m.created_at, now)),
  )
}

/** One row of the list, everything the screen needs as plain values (the row component draws, it does not decide). */
export interface AnnotationRowView {
  id: string
  kind: MarkKind
  page: number
  heading: string
  color: ColorKey | null
  colorName: string
  /** "yellow (Formula)": the colour as words, with the student's name for it. Empty for kinds without a colour. */
  colorText: string
  chapter: string | null
  tags: TagRef[]
  preview: string
  /** The preview is longer than the three lines the row shows. */
  clamped: boolean
  hasCard: boolean
  /** Made on this device and not yet confirmed by the server. */
  unsynced: boolean
  /** What a screen reader says for the row. */
  label: string
}

const CLAMP_CHARS = 180

export function toRow(mark: MarkRecord, legend: Legend): AnnotationRowView {
  const full = markPreview(mark, 2000)
  const filed = mark.link.chapter_id !== null || mark.link.chapter_key !== null
  return {
    id: mark.id,
    kind: mark.kind,
    page: mark.page,
    heading: markHeading(mark),
    color: mark.color,
    colorName: colorName(mark.color, legend),
    colorText: colorPhrase(mark.color, legend),
    chapter: filed ? shortLinkLabel(mark.link) : null,
    tags: mark.tags,
    preview: full,
    clamped: full.length > CLAMP_CHARS,
    hasCard: mark.recall_card_id !== null,
    unsynced: mark.local_only === true,
    label: describeMark(mark, legend),
  }
}

export const toRows = (marks: readonly MarkRecord[], legend: Legend) => marks.map((m) => toRow(m, legend))

/** The tags used by these marks, once each, by name: the options of the tag filter. */
export function tagsOf(marks: readonly MarkRecord[]): TagRef[] {
  const seen = new Map<string, TagRef>()
  for (const m of marks) for (const t of m.tags) seen.set(t.id, t)
  return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name))
}
