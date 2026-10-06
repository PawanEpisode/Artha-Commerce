import { toast, toastStore } from '@artha/design-system'
import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { track } from './analytics'
import { useToastAnalytics } from './toastAnalytics'

vi.mock('./analytics', () => ({ track: vi.fn() }))

beforeEach(() => {
  toastStore.reset()
  vi.mocked(track).mockClear()
})

describe('useToastAnalytics', () => {
  it('sends the id and variant, never the text, and always keeps errors', () => {
    renderHook(() => useToastAnalytics(() => 0.99))
    toast.error('Secret text', { id: 'profile-avatar' })
    expect(track).toHaveBeenCalledWith('toast_shown', { key: 'profile-avatar', variant: 'error' })
  })

  it('samples successes', () => {
    renderHook(() => useToastAnalytics(() => 0.5))
    toast.success('Saved', { id: 'profile-name' })
    expect(track).not.toHaveBeenCalled()
    renderHook(() => useToastAnalytics(() => 0.05))
    toast.success('Saved', { id: 'profile-name' })
    expect(track).toHaveBeenCalledTimes(1)
  })

  it('skips toasts without a stable id and stops after unmount', () => {
    const { unmount } = renderHook(() => useToastAnalytics(() => 0))
    toast.error('No id')
    expect(track).not.toHaveBeenCalled()
    unmount()
    toast.error('Later', { id: 'x' })
    expect(track).not.toHaveBeenCalled()
  })
})
