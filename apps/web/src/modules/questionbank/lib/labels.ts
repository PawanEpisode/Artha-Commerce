import type { QuestionKind } from './types'

export const QUESTION_KIND_LABELS: Record<QuestionKind, string> = {
  mcq_single: 'MCQ Single Choice',
  mcq_multi: 'MCQ Multiple Choice',
  true_false: 'True / False',
  numeric: 'Numeric',
  case_study: 'Case Study',
  long_form: 'Long Form',
  practical: 'Practical',
}

/** Human label for a kind enum; unknown values fall back to a title-cased version, never the raw enum. */
export function kindLabel(kind: string): string {
  const known = (QUESTION_KIND_LABELS as Record<string, string>)[kind]
  if (known) return known
  const words = kind.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export const DIFFICULTY_LABELS: Record<number, string> = {
  1: 'Foundational',
  2: 'Easy',
  3: 'Moderate',
  4: 'Hard',
  5: 'Exam level',
}

/** "1 mark" / "2 marks" / "0.5 marks". */
export function formatMarks(marks: number | string): string {
  const n = Number(marks)
  return `${n} ${n === 1 ? 'mark' : 'marks'}`
}

/**
 * Question stems, options and explanations are UI text, not long-form reading: sans, 14px. `RichText` always adds
 * `prose-reading` (serif, 17px), and both rules live in the same layer, so these use the important modifier.
 */
export const QUESTION_TEXT_CLASS = 'max-w-none! font-sans! text-[14px]! leading-6! [&_p]:my-0! [&_p+p]:mt-2!'

/** The numeric answer key as text, or null for a question that has none (every non-numeric kind). */
export function numericKeyText(key: unknown): string | null {
  if (key === null || key === undefined) return null
  if (typeof key === 'number' || typeof key === 'string') return String(key)
  if (typeof key === 'object' && 'value' in key && key.value !== null && key.value !== undefined) {
    const unit = 'unit' in key && typeof key.unit === 'string' && key.unit ? ` ${key.unit}` : ''
    return `${String(key.value)}${unit}`
  }
  return null
}
