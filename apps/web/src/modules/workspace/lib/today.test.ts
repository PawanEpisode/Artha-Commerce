import { describe, expect, it } from 'vitest'

import { todayAction } from './today'

describe('todayAction', () => {
  it('resumes whichever timer is running', () => {
    expect(todayAction({ live: 'pomodoro', focusOn: true, doneSeconds: 0 })).toMatchObject({
      to: '/app/focus',
      label: 'Resume timer',
    })
    expect(todayAction({ live: 'stopwatch', focusOn: false, doneSeconds: 600 })).toMatchObject({ to: '/app/tracker' })
  })
  it('starts a round, with day-one wording before any time is logged', () => {
    expect(todayAction({ live: 'none', focusOn: true, doneSeconds: 0 })).toMatchObject({
      label: 'Start your first round',
    })
    expect(todayAction({ live: 'none', focusOn: true, doneSeconds: 60 })).toMatchObject({ label: 'Start focus round' })
  })
  it('offers no primary action when the focus timer is off', () => {
    expect(todayAction({ live: 'none', focusOn: false, doneSeconds: 0 })).toEqual({ kind: 'none' })
  })
})
