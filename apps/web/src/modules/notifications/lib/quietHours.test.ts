import { describe, expect, it } from 'vitest'

import { crossesMidnight, describeQuietHours, formatTime, isValidTime, quietHoursError } from './quietHours'

describe('quiet hours helpers', () => {
  it('validates HH:MM like the API', () => {
    for (const ok of ['00:00', '07:05', '22:00', '23:59']) expect(isValidTime(ok)).toBe(true)
    for (const bad of ['', '24:00', '7:00', '07:60', '22:00:00', 'ab:cd']) expect(isValidTime(bad)).toBe(false)
  })

  it('formats a 24 hour time for reading', () => {
    expect(formatTime('00:00')).toBe('12:00 am')
    expect(formatTime('07:05')).toBe('7:05 am')
    expect(formatTime('12:00')).toBe('12:00 pm')
    expect(formatTime('22:30')).toBe('10:30 pm')
    expect(formatTime('nonsense')).toBe('nonsense')
  })

  it('knows a window that crosses midnight', () => {
    expect(crossesMidnight('22:00', '07:00')).toBe(true)
    expect(crossesMidnight('13:00', '15:00')).toBe(false)
  })

  it('refuses equal and malformed times, as the API does', () => {
    expect(quietHoursError('22:00', '07:00')).toBeNull()
    expect(quietHoursError('09:00', '09:00')).toMatch(/different/)
    expect(quietHoursError('9am', '07:00')).toMatch(/Enter a time/)
  })

  it('describes the window in words', () => {
    expect(describeQuietHours('22:00', '07:00')).toBe('Quiet from 10:00 pm until 7:00 am the next morning.')
    expect(describeQuietHours('13:00', '15:00')).toBe('Quiet from 1:00 pm until 3:00 pm.')
  })
})
