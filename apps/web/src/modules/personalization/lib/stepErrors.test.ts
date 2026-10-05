import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { describeStepError } from './stepErrors'

const failure = (status: number, error?: object) => new ApiError(status, 'x', error ? { error } : undefined)

describe('describeStepError', () => {
  it('shows field messages from validation', () => {
    const result = describeStepError(
      failure(400, { code: 'invalid', message: 'Invalid.', details: { full_name: ['Enter your name.'] } }),
    )
    expect(result.fields).toEqual({ full_name: 'Enter your name.' })
  })
  it('uses a `detail` message as the sentence', () => {
    expect(
      describeStepError(failure(400, { code: 'invalid', details: { detail: ['Choose your course first.'] } })).message,
    ).toBe('Choose your course first.')
  })
  it('hides server errors behind a calm sentence', () => {
    expect(describeStepError(failure(500, { message: 'Traceback…' })).message).toBe(
      'We could not save that. Please try again.',
    )
  })
  it('names offline, throttle and flag-off cases', () => {
    expect(describeStepError(new ApiError(0, 'net')).message).toContain('offline')
    expect(describeStepError(failure(429)).message).toContain('Too many')
    expect(describeStepError(failure(403, { code: 'feature_disabled' })).message).toContain('not available')
  })
  it('handles non-API errors', () => {
    expect(describeStepError(new Error('x')).message).toContain('could not save')
  })
})
