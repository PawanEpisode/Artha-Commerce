import { describe, expect, it } from 'vitest'

import { otherLiveLabel } from './live'

describe('otherLiveLabel', () => {
  it('treats an idle answer as no timer', () => {
    expect(otherLiveLabel(null)).toBeNull()
    expect(otherLiveLabel(undefined)).toBeNull()
    expect(otherLiveLabel('')).toBeNull()
    expect(otherLiveLabel('none')).toBeNull()
  })

  it('names the focus timer in plain words', () => {
    expect(otherLiveLabel('pomodoro')).toBe('focus')
    expect(otherLiveLabel('stopwatch')).toBe('stopwatch')
  })
})
