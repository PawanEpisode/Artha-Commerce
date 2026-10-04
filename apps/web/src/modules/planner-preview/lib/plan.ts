export interface PlanInput {
  subjects: string[]
  months: number
  hoursPerDay: number
}

export interface PlanPhase {
  key: 'learn' | 'revise' | 'mock'
  label: string
  share: number
  hours: number
}

export interface PlanResult {
  totalHours: number
  studyDays: number
  phases: PlanPhase[]
  perSubject: Array<{ name: string; hours: number }>
}

const PHASES: Array<Pick<PlanPhase, 'key' | 'label' | 'share'>> = [
  { key: 'learn', label: 'Learn', share: 0.55 },
  { key: 'revise', label: 'Revise', share: 0.25 },
  { key: 'mock', label: 'Mock tests', share: 0.2 },
]

/** Pure function: easy to unit test and to reuse in the real planner later. One rest day a week is assumed. */
export function buildPlan({ subjects, months, hoursPerDay }: PlanInput): PlanResult {
  const studyDays = Math.round(months * 30 * (6 / 7))
  const totalHours = Math.round(studyDays * hoursPerDay)
  const each = subjects.length ? totalHours / subjects.length : 0
  return {
    totalHours,
    studyDays,
    phases: PHASES.map((p) => ({ ...p, hours: Math.round(totalHours * p.share) })),
    perSubject: subjects.map((name) => ({ name, hours: Math.round(each) })),
  }
}
