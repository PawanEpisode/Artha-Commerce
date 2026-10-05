import type { SyllabusChapter } from './types'

/** "5 to 8 marks", "6 marks" or null when the chapter has no published weightage. */
export function marksLabel(chapter: Pick<SyllabusChapter, 'marks_min' | 'marks_max'>): string | null {
  const min = chapter.marks_min === null ? null : Number(chapter.marks_min)
  const max = chapter.marks_max === null ? null : Number(chapter.marks_max)
  if (min !== null && max !== null && min !== max) return `${min} to ${max} marks`
  const single = max ?? min
  return single === null ? null : `${single} mark${single === 1 ? '' : 's'}`
}

/** Papers with more chapters than this get a search box. */
export const SEARCH_THRESHOLD = 8

/** Case-insensitive match of a search box against a name. An empty query matches everything. */
export function matchesQuery(name: string, query: string): boolean {
  const q = query.trim().toLowerCase()
  return q === '' || name.toLowerCase().includes(q)
}

export function pluralize(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

/** Groups consecutive items by their `section` label, keeping order. Items without a section share one unnamed group. */
export function groupBySection<T extends { section?: string }>(items: T[]): Array<{ section: string; items: T[] }> {
  const groups: Array<{ section: string; items: T[] }> = []
  for (const item of items) {
    const section = item.section ?? ''
    const last = groups[groups.length - 1]
    if (last && last.section === section) last.items.push(item)
    else groups.push({ section, items: [item] })
  }
  return groups
}
