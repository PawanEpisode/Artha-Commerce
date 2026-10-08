/** Cloze parsing: `{{c1::answer}}` or `{{c1::answer::hint}}`. Twin of the parser in `domain/cards.py`. */

import { MAX_CLOZES } from './limits'

/** A fresh regex per call: a shared global regex keeps `lastIndex` between uses. */
export const clozePattern = (): RegExp => /\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}/gs

export function clozeNumbers(text: string): number[] {
  return [...text.matchAll(clozePattern())].map((m) => Number(m[1]))
}

export interface ClozeIssue {
  code: 'cloze_none' | 'cloze_too_many' | 'cloze_duplicate' | 'cloze_gap'
  message: string
}

export function clozeIssues(text: string): ClozeIssue[] {
  const numbers = clozeNumbers(text)
  if (numbers.length === 0) return [{ code: 'cloze_none', message: 'Add at least one {{c1::...}} deletion.' }]
  if (numbers.length > MAX_CLOZES)
    return [{ code: 'cloze_too_many', message: `At most ${MAX_CLOZES} deletions are allowed.` }]
  if (new Set(numbers).size !== numbers.length)
    return [{ code: 'cloze_duplicate', message: 'Each deletion needs its own number: c1, c2, c3 ...' }]
  const sorted = [...numbers].sort((a, b) => a - b)
  if (sorted.some((n, i) => n !== i + 1))
    return [{ code: 'cloze_gap', message: 'Deletion numbers must run 1, 2, 3 ... without gaps.' }]
  return []
}
