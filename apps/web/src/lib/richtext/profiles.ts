/**
 * Rich text is sanitised Markdown plus KaTeX, nothing else is stored. A profile says what a given feature may contain.
 * This file is the twin of `apps/api/core/richtext.py` (the authority): same limits, same rules, and the shared
 * conformance corpus `apps/api/core/tests/richtext_cases.json` runs against both, so a difference fails a test.
 */

export type RichTextProfile = 'question' | 'note' | 'card'

export interface ProfileRules {
  maxChars: number
  maxImages: number
  /** Body rows, not counting the header. */
  maxTableRows: number
  maxTableCols: number
  /** Allowed ATX heading levels (min, max), or null when headings are not allowed. */
  headings: readonly [number, number] | null
  taskLists: boolean
  rules: boolean
  /** A missing alt text is an error (questions) or a warning (notes: the editor offers "mark decorative"). */
  altRequired: boolean
  maxMathChars: number
  maxMathCount: number
}

export const PROFILES: Record<RichTextProfile, ProfileRules> = {
  question: {
    maxChars: 20_000,
    maxImages: 12,
    maxTableRows: 40,
    maxTableCols: 12,
    headings: null,
    taskLists: false,
    rules: false,
    altRequired: true,
    maxMathChars: 2000,
    maxMathCount: 200,
  },
  note: {
    maxChars: 100_000,
    maxImages: 40,
    maxTableRows: 100,
    maxTableCols: 12,
    headings: [2, 4],
    taskLists: true,
    rules: true,
    altRequired: false,
    maxMathChars: 2000,
    maxMathCount: 200,
  },
  /** A recall card field (F-15): short, no images in R1, small tables. Twin of `CARD` in `core/richtext.py`. */
  card: {
    maxChars: 4000,
    maxImages: 0,
    maxTableRows: 10,
    maxTableCols: 6,
    headings: null,
    taskLists: false,
    rules: false,
    altRequired: false,
    maxMathChars: 1000,
    maxMathCount: 40,
  },
}
