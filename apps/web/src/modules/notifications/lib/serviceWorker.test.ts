import { describe, expect, it } from 'vitest'

import { shouldAutoRegister } from './serviceWorker'

describe('shouldAutoRegister', () => {
  it('registers in production builds', () => {
    expect(shouldAutoRegister({ production: true, swDev: false, supported: true })).toBe(true)
  })
  it('registers in development only with VITE_SW_DEV', () => {
    expect(shouldAutoRegister({ production: false, swDev: false, supported: true })).toBe(false)
    expect(shouldAutoRegister({ production: false, swDev: true, supported: true })).toBe(true)
  })
  it('never registers where service workers do not exist', () => {
    expect(shouldAutoRegister({ production: true, swDev: true, supported: false })).toBe(false)
  })
})
