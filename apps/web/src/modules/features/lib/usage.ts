/** Which catalog tools a student has used, from facts other modules already expose. Pure. */
export interface UsageSignals {
  /** At least one chapter has progress. */
  startedChapters: boolean
  /** At least one study session of any kind. */
  anySession: boolean
  /** At least one finished Pomodoro round. */
  pomodoroSession: boolean
}

export function usedTools({ startedChapters, anySession, pomodoroSession }: UsageSignals): Set<string> {
  const used = new Set<string>()
  if (startedChapters) used.add('syllabus-tracker')
  if (anySession) {
    used.add('time-tracker')
    used.add('streaks-analytics')
  }
  if (pomodoroSession) used.add('pomodoro-focus-timer')
  return used
}
