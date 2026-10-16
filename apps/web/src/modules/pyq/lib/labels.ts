import type { SchemeRelation } from './types'

const TERM_NAMES: Record<string, string> = {
  june: 'June',
  dec: 'December',
  may: 'May',
  nov: 'November',
}

/** "dec_2023" -> "December 2023". Unknown shapes fall back to the upper-cased code. */
export function termLabel(code: string): string {
  const [name, year] = code.split('_')
  if (!name) return code
  return [TERM_NAMES[name] ?? name.toUpperCase(), year].filter(Boolean).join(' ')
}

/** "cma_intermediate" -> "CMA INTERMEDIATE". */
export const levelLabel = (code: string) => code.replace(/_/g, ' ').toUpperCase()

/** Marks arrive as decimal strings ("2.0"). */
export function marksText(marks: string | number): string {
  const n = Number(marks)
  return Number.isFinite(n) ? String(n) : String(marks)
}

export const SCHEME_BADGES: Record<SchemeRelation, { label: string; className: string }> = {
  current: { label: '2022 Syllabus', className: 'border-success-border bg-success-bg text-success-fg' },
  mapped: { label: 'Mapped', className: 'border-info-border bg-info-bg text-info-fg' },
  changed: { label: 'Changed in 2022', className: 'border-warning-border bg-warning-bg text-warning-fg' },
  unmapped: { label: 'Out of Syllabus', className: 'border-border bg-muted text-muted-foreground' },
}
