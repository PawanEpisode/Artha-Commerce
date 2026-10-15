/** The "Pick your attempt" card (PRD 7.3): which terms to offer and whether a typed date is acceptable. Pure. */

export interface TermOption {
  id: string
  name: string
  exam_start: string | null
}

/** Terms whose exams are still ahead, soonest first, at most `limit`. A term with no date is offered last (the student still knows it). */
export function upcomingTerms<T extends TermOption>(terms: readonly T[], today: string, limit = 4): T[] {
  const ahead = terms.filter((t) => t.exam_start === null || t.exam_start > today)
  const dated = ahead
    .filter((t) => t.exam_start !== null)
    .sort((a, b) => (a.exam_start as string).localeCompare(b.exam_start as string))
  return [...dated, ...ahead.filter((t) => t.exam_start === null)].slice(0, limit)
}

/** An error message for a typed exam date, or null when it is fine: a real date after today. */
export function examDateError(value: string, today: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return 'Pick a date.'
  const [y, m, d] = value.split('-').map(Number)
  const real = new Date(Date.UTC(y, m - 1, d))
  if (real.getUTCFullYear() !== y || real.getUTCMonth() !== m - 1 || real.getUTCDate() !== d)
    return 'That date does not exist.'
  return value > today ? null : 'Pick a date after today.'
}

/** Whole days from `today` to `target`, both `YYYY-MM-DD`. */
export function daysBetween(today: string, target: string): number {
  const ms = (s: string) => Date.UTC(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10)))
  return Math.round((ms(target) - ms(today)) / 86_400_000)
}

/** Whether the card should be offered: a plan with no exam date, and the student has not dismissed it on this device. */
export const shouldOfferExamCard = (daysToExam: number | null, dismissed: boolean) => daysToExam === null && !dismissed

const KEY = 'artha:today:exam-card-dismissed'
export function examCardDismissed(): boolean {
  try {
    return window.localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}
export function dismissExamCard(): void {
  try {
    window.localStorage.setItem(KEY, '1')
  } catch {
    /* a private window: the card returns next visit, which is fine */
  }
}
