/**
 * The step list of the onboarding flow as pure functions: which steps one student walks, which step a URL may open,
 * where Back and Continue go. The server decides what is satisfied (facts over flags); this only orders and guards.
 */

export type StepStateName = 'todo' | 'done' | 'skipped' | 'unavailable'
export type FlowMode = 'full' | 'update'

export interface StepInfo {
  key: string
  state: StepStateName
  mandatory: boolean
  available: boolean
}

export interface StepCopy {
  /** Short label in the progress bar. */
  label: string
  title: string
  description?: string
}

export const STEP_COPY: Record<string, StepCopy> = {
  profile: { label: 'You', title: 'What should we call you?', description: 'Your name appears in your workspace.' },
  course: {
    label: 'Course',
    title: 'Which exam are you preparing for?',
    description: 'We build your syllabus map from it.',
  },
  hours: {
    label: 'Time',
    title: 'How much can you study each day?',
    description: 'A realistic number beats a big one.',
  },
  targets: {
    label: 'Targets',
    title: 'How thoroughly will you prepare each chapter?',
    description: 'Pick a plan. You can change it any time in Coverage settings.',
  },
  catchup: {
    label: 'Catch up',
    title: 'What have you already covered?',
    description: 'Tick the chapters you have finished. This gives you a real starting point.',
  },
  avatar: {
    label: 'Photo',
    title: 'Add a face to your workspace',
    description: 'A photo or an avatar. You can skip this.',
  },
}

/** Keys the web has a screen for. A step the server lists that is not here (a later feature) is not walked. */
export const KNOWN_STEPS = Object.keys(STEP_COPY)

export const copyFor = (key: string): StepCopy => STEP_COPY[key] ?? { label: key, title: key }

/**
 * Steps this student walks, fixed when the flow opens so the progress bar does not shrink as steps get done.
 * A new student walks every available step; a returning student (`update`) only the mandatory ones still to do.
 */
export function walkOf(mode: FlowMode, steps: ReadonlyArray<StepInfo>): string[] {
  return steps
    .filter((s) => s.available && KNOWN_STEPS.includes(s.key))
    .filter((s) => (mode === 'full' ? true : s.mandatory && s.state === 'todo'))
    .map((s) => s.key)
}

const stateOf = (steps: ReadonlyArray<StepInfo>, key: string) => steps.find((s) => s.key === key)

/** The first mandatory step in the walk that is still to do: nothing after it may be opened. */
export function firstBlocking(walk: ReadonlyArray<string>, steps: ReadonlyArray<StepInfo>): string | null {
  return (
    walk.find((key) => {
      const s = stateOf(steps, key)
      return s?.mandatory && s.state === 'todo'
    }) ?? null
  )
}

/** The first step still to do (mandatory first by order, then unseen optional ones). Null when all are handled. */
export function firstTodo(walk: ReadonlyArray<string>, steps: ReadonlyArray<StepInfo>): string | null {
  return walk.find((key) => stateOf(steps, key)?.state === 'todo') ?? null
}

/** Which step the URL may show: the requested one if it is in the walk and not past a missing mandatory step. */
export function resolveStep(
  walk: ReadonlyArray<string>,
  steps: ReadonlyArray<StepInfo>,
  requested: string | undefined,
): { key: string | null; redirected: boolean } {
  const blocking = firstBlocking(walk, steps)
  if (requested && walk.includes(requested)) {
    const allowed = blocking === null || walk.indexOf(requested) <= walk.indexOf(blocking)
    if (allowed) return { key: requested, redirected: false }
  }
  const key = blocking ?? firstTodo(walk, steps)
  return { key, redirected: requested !== undefined && requested !== key }
}

export const nextAfter = (walk: ReadonlyArray<string>, key: string): string | null =>
  walk[walk.indexOf(key) + 1] ?? null
export const previousBefore = (walk: ReadonlyArray<string>, key: string): string | null =>
  walk.indexOf(key) > 0 ? (walk[walk.indexOf(key) - 1] ?? null) : null
