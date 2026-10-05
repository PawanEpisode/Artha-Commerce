import { beforeEach, describe, expect, it } from 'vitest'

import { apiErrorMessage } from './api-error-message'
import { DEFAULT_DURATION, MAX_VISIBLE, toast, toastStore } from './toast-store'

beforeEach(() => toastStore.reset())

describe('toast store', () => {
  it('adds toasts with per-variant durations', () => {
    toast.success('Saved')
    toast.error('Failed')
    const [a, b] = toastStore.getSnapshot()
    expect(a?.duration).toBe(DEFAULT_DURATION.success)
    expect(b?.duration).toBe(DEFAULT_DURATION.error)
    expect(DEFAULT_DURATION.error).toBeGreaterThan(DEFAULT_DURATION.success)
  })
  it('de-duplicates by id and restarts the timer revision', () => {
    toast.info('One', { id: 'x' })
    toast.info('Two', { id: 'x' })
    const all = toastStore.getSnapshot()
    expect(all).toHaveLength(1)
    expect(all[0]?.title).toBe('Two')
    expect(all[0]?.revision).toBe(2)
  })
  it('caps the visible stack', () => {
    for (let i = 0; i < MAX_VISIBLE + 2; i++) toast.info(`n${i}`)
    expect(toastStore.getSnapshot().filter((t) => !t.dismissed)).toHaveLength(MAX_VISIBLE)
  })
  it('dismisses one or all, then removes', () => {
    const id = toast.success('A')
    toast.success('B')
    toast.dismiss(id)
    expect(toastStore.getSnapshot()[0]?.dismissed).toBe(true)
    toast.dismiss()
    expect(toastStore.getSnapshot().every((t) => t.dismissed)).toBe(true)
    toastStore.remove(id)
    expect(toastStore.getSnapshot()).toHaveLength(1)
  })
  it('promise moves loading to success or error on the same toast', async () => {
    await toast.promise(Promise.resolve(3), { loading: 'Saving', success: (n) => `Saved ${n}`, error: 'No' })
    await Promise.resolve()
    const [t] = toastStore.getSnapshot()
    expect(t?.variant).toBe('success')
    expect(t?.title).toBe('Saved 3')
    toastStore.reset()
    await toast
      .promise(Promise.reject(new Error('x')), { loading: 'Saving', success: 'ok', error: 'Nope' })
      .catch(() => {})
    await Promise.resolve()
    expect(toastStore.getSnapshot()[0]?.variant).toBe('error')
  })
})

describe('apiErrorMessage', () => {
  const err = (status: number, body?: unknown) => ({ status, body })
  it('prefers the envelope message for validation errors', () => {
    expect(apiErrorMessage(err(409, { error: { code: 'target_met', message: 'Target reached.' } }), 'fb')).toBe(
      'Target reached.',
    )
  })
  it('falls back to the first field detail', () => {
    expect(
      apiErrorMessage(err(400, { error: { message: 'Request failed.', details: { score: ['Too high.'] } } }), 'fb'),
    ).toBe('Too high.')
  })
  it('maps statuses', () => {
    expect(apiErrorMessage(err(401), 'fb')).toMatch(/sign in/)
    expect(apiErrorMessage(err(429), 'fb')).toMatch(/Too many/)
    expect(apiErrorMessage(err(503), 'fb')).toMatch(/our side/)
    expect(apiErrorMessage(err(400), 'fb')).toBe('fb')
  })
  it('handles offline and unknown errors', () => {
    expect(apiErrorMessage(new TypeError('Failed to fetch'), 'fb')).toMatch(/offline/)
    expect(apiErrorMessage('boom', 'fb')).toBe('fb')
  })
})
