import { describe, expect, it } from 'vitest'

import { type SessionFormValues, toEdit, toManualInput, validateForm } from './sessionForm'
import type { StudySession } from './types'

const TZ = 'Asia/Kolkata'
const NOW = Date.parse('2026-10-05T04:30:00Z') // 10:00 in India

const base: SessionFormValues = {
  mode: 'range',
  start: '2026-10-05T08:00',
  end: '2026-10-05T09:00',
  durationMinutes: 60,
  subject_id: null,
  chapter_id: null,
  activity_type: 'reading',
  note: '',
  onOverlap: null,
  confirmOld: false,
}

describe('validateForm', () => {
  it('accepts a normal range', () => {
    expect(validateForm(base, TZ, NOW)).toEqual({})
  })
  it('rejects an end before the start and a span under one minute', () => {
    expect(validateForm({ ...base, end: '2026-10-05T07:00' }, TZ, NOW).end).toMatch(/after the start/)
    expect(validateForm({ ...base, end: '2026-10-05T08:00' }, TZ, NOW).end).toBeDefined()
  })
  it('rejects the future beyond the clock-skew allowance', () => {
    expect(validateForm({ ...base, start: '2026-10-05T09:00', end: '2026-10-05T11:00' }, TZ, NOW).end).toMatch(/future/)
  })
  it('rejects more than 24 hours', () => {
    expect(validateForm({ ...base, start: '2026-10-03T08:00', end: '2026-10-05T08:30' }, TZ, NOW).end).toMatch(
      /24 hours/,
    )
  })
  it('checks the duration in duration mode', () => {
    expect(validateForm({ ...base, mode: 'duration', durationMinutes: 0 }, TZ, NOW).duration).toBeDefined()
    expect(validateForm({ ...base, mode: 'duration', durationMinutes: 1500 }, TZ, NOW).duration).toMatch(/24 hours/)
    expect(validateForm({ ...base, mode: 'duration', durationMinutes: 30 }, TZ, NOW)).toEqual({})
  })
  it('rejects a note over 500 characters', () => {
    expect(validateForm({ ...base, note: 'x'.repeat(501) }, TZ, NOW).note).toBeDefined()
  })
})

describe('toManualInput', () => {
  it('sends instants and the idempotency key', () => {
    const input = toManualInput(base, TZ, 'cid')
    expect(input.client_id).toBe('cid')
    expect(input.started_at).toBe('2026-10-05T02:30:00.000Z')
    expect(input.ended_at).toBe('2026-10-05T03:30:00.000Z')
    expect(input.duration_seconds).toBeUndefined()
  })
  it('sends a duration instead of an end in duration mode', () => {
    const input = toManualInput({ ...base, mode: 'duration', durationMinutes: 45 }, TZ, 'cid')
    expect(input.duration_seconds).toBe(2700)
    expect(input.ended_at).toBeUndefined()
  })
})

describe('toEdit', () => {
  const original = {
    started_at: '2026-10-05T02:30:00Z',
    ended_at: '2026-10-05T03:30:00Z',
    subject_id: null,
    chapter_id: null,
    activity_type: 'reading',
    note: 'old',
  } as StudySession

  it('sends nothing when nothing changed', () => {
    expect(toEdit({ ...base, note: 'old' }, TZ, original)).toEqual({})
  })
  it('sends only the changed fields', () => {
    expect(toEdit({ ...base, note: 'new' }, TZ, original)).toEqual({ note: 'new' })
    expect(toEdit({ ...base, note: 'old', end: '2026-10-05T09:30' }, TZ, original)).toEqual({
      ended_at: '2026-10-05T04:00:00.000Z',
    })
  })
})
