import type { SyllabusChapter } from './types'

/** "5 to 8 marks", "6 marks" or null when the chapter has no published weightage. */
export function marksLabel(chapter: Pick<SyllabusChapter, 'marks_min' | 'marks_max'>): string | null {
  const min = chapter.marks_min === null ? null : Number(chapter.marks_min)
  const max = chapter.marks_max === null ? null : Number(chapter.marks_max)
  if (min !== null && max !== null && min !== max) return `${min} to ${max} marks`
  const single = max ?? min
  return single === null ? null : `${single} mark${single === 1 ? '' : 's'}`
}

export function pluralize(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}
