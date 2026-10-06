export type TodayAction =
  | { kind: 'resume'; to: '/app/focus' | '/app/tracker'; label: string }
  | { kind: 'start'; to: '/app/focus'; label: string }
  | { kind: 'none' }

interface Input {
  live: 'none' | 'stopwatch' | 'pomodoro'
  focusOn: boolean
  doneSeconds: number
}

/**
 * The one primary button of the Today card (PRD 7.3): resume what is running, otherwise start a round. Day one
 * says "Start your first round". With the focus timer switched off there is no primary action, only "Log time".
 */
export function todayAction({ live, focusOn, doneSeconds }: Input): TodayAction {
  if (live === 'pomodoro') return { kind: 'resume', to: '/app/focus', label: 'Resume timer' }
  if (live === 'stopwatch') return { kind: 'resume', to: '/app/tracker', label: 'Resume timer' }
  if (!focusOn) return { kind: 'none' }
  return { kind: 'start', to: '/app/focus', label: doneSeconds > 0 ? 'Start focus round' : 'Start your first round' }
}
