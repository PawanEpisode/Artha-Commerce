/** The most questions one quick session can hold. Keep equal to `MAX_QUICK_PRACTICE_COUNT` in the API serializers. */
export const MAX_PRACTICE_COUNT = 100

const STEPS = [10, 20, 50, MAX_PRACTICE_COUNT]

export interface PracticeCountOption {
  value: number
  label: string
}

/**
 * How many questions a student can ask for in a chapter holding `available`: the usual steps that fit, then the whole
 * chapter when it fits in one session (or the session maximum when it does not). Empty for a chapter with no questions.
 */
export function practiceCountOptions(available: number): PracticeCountOption[] {
  if (!Number.isFinite(available) || available < 1) return []
  const whole = Math.min(Math.floor(available), MAX_PRACTICE_COUNT)
  const values = [...new Set([...STEPS.filter((n) => n < whole), whole])]
  return values.map((value) => ({
    value,
    label: value === whole && whole === Math.floor(available) ? `All ${value}` : `${value} questions`,
  }))
}

/** 10 when the chapter has that many, otherwise everything it has. */
export function defaultPracticeCount(options: PracticeCountOption[]): number | undefined {
  return (options.find((o) => o.value === 10) ?? options[options.length - 1])?.value
}
