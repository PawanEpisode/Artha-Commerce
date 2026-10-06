import { describe, expect, it } from 'vitest'

import { usedTools } from './usage'

describe('usedTools', () => {
  it('starts empty', () => {
    expect(usedTools({ startedChapters: false, anySession: false, pomodoroSession: false }).size).toBe(0)
  })
  it('maps each signal to its tools', () => {
    expect([...usedTools({ startedChapters: true, anySession: false, pomodoroSession: false })]).toEqual([
      'syllabus-tracker',
    ])
    expect([...usedTools({ startedChapters: false, anySession: true, pomodoroSession: false })]).toEqual([
      'time-tracker',
      'streaks-analytics',
    ])
    expect([...usedTools({ startedChapters: false, anySession: true, pomodoroSession: true })]).toContain(
      'pomodoro-focus-timer',
    )
  })
})
