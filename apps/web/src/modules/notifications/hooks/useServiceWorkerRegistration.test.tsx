import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ production: true, swDev: undefined as string | undefined }))
vi.mock('~/lib/env', () => ({
  get isProduction() {
    return state.production
  },
  env: {
    get VITE_SW_DEV() {
      return state.swDev
    },
  },
}))

import { useServiceWorkerRegistration } from './useServiceWorkerRegistration'

const register = vi.fn()
const original = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')

beforeEach(() => {
  register.mockReset().mockResolvedValue({})
  Object.defineProperty(navigator, 'serviceWorker', { value: { register }, configurable: true })
  state.production = true
  state.swDev = undefined
})
afterEach(() => {
  if (original) Object.defineProperty(navigator, 'serviceWorker', original)
  else delete (navigator as unknown as Record<string, unknown>).serviceWorker
})

describe('useServiceWorkerRegistration', () => {
  it('registers /sw.js at the site root, always fetching it fresh, in a production build', () => {
    renderHook(() => useServiceWorkerRegistration())
    expect(register).toHaveBeenCalledWith('/sw.js', { scope: '/', updateViaCache: 'none' })
  })

  it('does not register in development by default, but does with VITE_SW_DEV=true', () => {
    state.production = false
    renderHook(() => useServiceWorkerRegistration())
    expect(register).not.toHaveBeenCalled()
    state.swDev = 'true'
    renderHook(() => useServiceWorkerRegistration())
    expect(register).toHaveBeenCalledTimes(1)
  })

  it('does nothing where service workers do not exist', () => {
    delete (navigator as unknown as Record<string, unknown>).serviceWorker
    expect(() => renderHook(() => useServiceWorkerRegistration())).not.toThrow()
  })

  it('does not let a failed registration break the page', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    register.mockRejectedValue(new Error('blocked'))
    expect(() => renderHook(() => useServiceWorkerRegistration())).not.toThrow()
    await Promise.resolve()
    await Promise.resolve()
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
})
